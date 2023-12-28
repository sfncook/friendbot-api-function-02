import logging
import azure.functions as func
import uuid
import json
import os
from typing import Any
import azure.cognitiveservices.speech as speechsdk
import base64
import asyncio
import tempfile
from datetime import datetime
from .query_llm import query_llm

cors_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "OPTIONS, POST, PUT",
    "Access-Control-Allow-Headers": "Content-Type",
}

azureVisemeIdToModelCodes = {
    0: {"target": "viseme_sil", "value": 1},
    1: {"target": "viseme_aa", "value": 1},
    2: {"target": "viseme_aa", "value": 1},
    3: {"target": "viseme_O", "value": 1},
    4: {"target": "viseme_O", "value": 0.7},
    5: {"target": "viseme_RR", "value": 1},
    6: {"target": "viseme_I", "value": 0.7},
    7: {"target": "viseme_U", "value": 1},
    8: {"target": "viseme_aa", "value": 0.8},
    9: {"target": "viseme_O", "value": 1},
    10: {"target": "viseme_aa", "value": 0.7},
    11: {"target": "viseme_aa", "value": 1},
    12: {"target": "viseme_RR", "value": 0.8},
    13: {"target": "viseme_O", "value": 1},
    14: {"target": "viseme_O", "value": 1},
    15: {"target": "viseme_SS", "value": 1},
    16: {"target": "viseme_CH", "value": 1},
    17: {"target": "viseme_TH", "value": 1},
    18: {"target": "viseme_FF", "value": 1},
    19: {"target": "viseme_DD", "value": 1},
    20: {"target": "viseme_kk", "value": 1},
    21: {"target": "viseme_PP", "value": 1},
}

async def audio_file_to_base64(file_path):
    with open(file_path, 'rb') as file:
        data = file.read()
        return base64.b64encode(data).decode('utf-8')


async def azure_speech(text, file_name, voice):
    try:
        speech_key = os.environ.get("AZURE_SPEECH_KEY")
        speech_region = os.environ.get("AZURE_SPEECH_REGION")
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_name)
        speech_config.speech_synthesis_voice_name = voice
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        viseme_data = []

        def on_viseme_received(e):
            viseme_data.append({
                "offset": e.audio_offset / 10000000.0,
                "visemeId": e.viseme_id
            })

        synthesizer.viseme_received.connect(on_viseme_received)
        synthesizer.speak_text_async(text).get()

        lipsync_data: dict[str, list[Any]] = {
            "mouthCues": [
                # example--> { "start": 0.00, "end": 0.01, "value": "X" },
            ]
        }
        prev_offset = 0

        for azure_viseme in viseme_data:
            model_code = azureVisemeIdToModelCodes[azure_viseme["visemeId"]]
            lipsync_data["mouthCues"].append({
                "start": prev_offset,
                "end": azure_viseme["offset"],
                "target": model_code['target'],
                "value": model_code['value']
            })
            prev_offset = azure_viseme["offset"]

        return {
            "lipsync": lipsync_data,
            "audio": await audio_file_to_base64(file_name)
        }
    except Exception as inst:
        logging.error("ERROR in azure_speech")
        print(type(inst))  # the exception type
        print(inst.args)  # arguments stored in .args
        print(inst)  # __str__ allows args to be printed directly,
        # but may be overridden in exception subclasses
        return {
            "lipsync": "",
            "audio": ""
        }


def convert_cosmos_messages_to_gpt_format(messages):
    converted_messages = []

    for message in messages:
        user_message = {
            "role": "user",
            "content": message["user_msg"]
        }
        assistant_message = {
            "role": "assistant",
            "content": message["assistant_response"]
        }

        converted_messages.append(user_message)
        converted_messages.append(assistant_message)

    return converted_messages
    # # Sort the converted messages by timestamp (oldest to newest)
    # sorted_messages = sorted(
    #     converted_messages,
    #     key=lambda x: x.get("timestamp", "")
    # )
    #
    # return sorted_messages


def add_message_to_convo(newmessage, convo_id, user_msg, assistant_response, total_tokens):
    new_msg = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "conversation_id": convo_id,
        "user_msg": user_msg,
        "assistant_response": assistant_response,
        "total_tokens": total_tokens
    }
    newmessage.set(func.Document.from_dict(new_msg))
    return new_msg


def update_user_data(updateconversation, conversation_obj, user_data):
    # Read the existing conversation object
    # conversation_obj = conversations_container.read_item(
    #     item=convo_id,
    #     partition_key=convo_id,
    # )

    # Check for changes or missing keys
    needs_update = False
    for key, value in user_data.items():
        # Special handling for 'hobbies' and 'interests', which are arrays
        if key in ["hobbies", "interests"]:
            if key not in conversation_obj:
                conversation_obj[key] = []

            # Split comma-separated string into a list and trim whitespace
            if isinstance(value, str):
                value = [item.strip() for item in value.split(',')]

            # Merge with existing list and de-duplicate
            updated_list = list(set(conversation_obj[key] + value))
            if updated_list != conversation_obj[key]:
                conversation_obj[key] = updated_list
                needs_update = True
        elif key not in conversation_obj or conversation_obj[key] != value:
            conversation_obj[key] = value
            needs_update = True

    # Update the item in Cosmos DB if needed
    if needs_update:
        try:
            updateconversation.set(func.Document.from_dict(conversation_obj))
        except Exception as e:
            logging.error(f"Error updating conversation: {e}")


def main(req: func.HttpRequest, inconversations: func.DocumentList, prevmessages: func.DocumentList,
         newmessage: func.Out[func.Document], updateconversation: func.Out[func.Document]) -> func.HttpResponse:
    method = req.method
    logging.info(f"submit_user_message {method}")

    if method == 'OPTIONS':
        return func.HttpResponse(headers=cors_headers)
    elif method == 'PUT':
        if not inconversations:
            logging.warning("inconversations item not found")
        else:
            conversation_obj = inconversations[0]
            convo_id = conversation_obj['id']

            try:
                req_body = req.get_json()
                user_msg = req_body.get("user_msg", "Hello!")
                mute = req_body.get("mute", False)
                avatar = req_body.get("avatar", {})
            except ValueError:
                return func.HttpResponse(
                    "Missing request body parameters (conversation_id, user_msg)",
                    status_code=400
                )
                pass

            logging.info(f"Many prevmessages:{len(prevmessages)}")
            logging.info("convo_id=%s", convo_id)
            logging.info("user_msg=%s", user_msg)
            logging.info("mute=%s", mute)

            gpt_msgs = convert_cosmos_messages_to_gpt_format(prevmessages)
            llm_resp = query_llm(user_msg, gpt_msgs, conversation_obj, avatar['name'])

            temp_dir = tempfile.gettempdir()
            temp_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False)
            logging.info(temp_file.name)

            assistant_response_text = llm_resp['assistant_response']['content']
            usage_total_tokens = llm_resp['usage']['total_tokens']
            user_data = llm_resp['user_data']

            if not mute:
                speech_resp = asyncio.run(azure_speech(assistant_response_text, temp_file.name, avatar['voice']))
            else:
                speech_resp = {
                    "lipsync": {},
                    "audio": ""
                }

            merged_data = {**llm_resp, **speech_resp}
            merged_json_resp = json.dumps(merged_data, separators=(',', ':'))

            add_message_to_convo(newmessage, convo_id, user_msg, assistant_response_text, usage_total_tokens)
            if user_data != {}:
                update_user_data(updateconversation, conversation_obj, user_data)

            logging.info(f"Response: SUCCESS")
            return func.HttpResponse(
                status_code=200,
                headers=cors_headers,
                body=merged_json_resp,
                mimetype="application/json"
            )
    else:
        logging.info(f"Response: FAILURE")
        return func.HttpResponse("Method not allowed", status_code=405)

import logging
import azure.functions as func
import uuid
import json
from openai import AzureOpenAI
import os
from typing import Any
import azure.cognitiveservices.speech as speechsdk
import base64
import asyncio
import tempfile

cors_headers = {
    "Access-Control-Allow-Origin": "*",  # Replace with your allowed origin(s)
    "Access-Control-Allow-Methods": "OPTIONS, POST",  # Add other allowed methods if needed
    "Access-Control-Allow-Headers": "Content-Type",
}

azureVisemeIdToModelCodes = {
    0: {"target":"viseme_sil", "value":1},
    1: {"target":"viseme_aa", "value":1},
    2: {"target":"viseme_aa", "value":1},
    3: {"target":"viseme_O", "value":1},
    4: {"target":"viseme_O", "value":0.7},
    5: {"target":"viseme_RR", "value":1},
    6: {"target":"viseme_I", "value":0.7},
    7: {"target":"viseme_U", "value":1},
    8: {"target":"viseme_aa", "value":0.8},
    9: {"target":"viseme_O", "value":1},
    10: {"target":"viseme_aa", "value":0.7},
    11: {"target":"viseme_aa", "value":1},
    12: {"target":"viseme_RR", "value":0.8},
    13: {"target":"viseme_O", "value":1},
    14: {"target":"viseme_O", "value":1},
    15: {"target":"viseme_SS", "value":1},
    16: {"target":"viseme_CH", "value":1},
    17: {"target":"viseme_TH", "value":1},
    18: {"target":"viseme_FF", "value":1},
    19: {"target":"viseme_DD", "value":1},
    20: {"target":"viseme_kk", "value":1},
    21: {"target":"viseme_PP", "value":1},
}


async def audio_file_to_base64(file_path):
    with open(file_path, 'rb') as file:
        data = file.read()
        return base64.b64encode(data).decode('utf-8')


async def azure_speech(text, file_name):
    try:
        speech_key = os.environ.get("AZURE_SPEECH_KEY")
        speech_region = os.environ.get("AZURE_SPEECH_REGION")
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_name)
        speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
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
        print("ERROR in azure_speech")
        print(type(inst))    # the exception type
        print(inst.args)     # arguments stored in .args
        print(inst)          # __str__ allows args to be printed directly,
        # but may be overridden in exception subclasses
        return {
            "lipsync": "",
            "audio": ""
        }

def main(req: func.HttpRequest, inconversations: func.DocumentList, prevmessages: func.DocumentList, message: func.Out[func.Document]) -> func.HttpResponse:
    method = req.method

    if method == 'OPTIONS':
        return func.HttpResponse(headers=cors_headers)
    else:
        if not inconversations:
            logging.warning("inconversations item not found")
        else:
            conversation_obj = inconversations[0]
            convo_id = conversation_obj['id']

            try:
                req_body = req.get_json()
                user_msg = req_body.get("user_msg", "Hello!")
                mute = req_body.get("mute", False)
            except ValueError:
                return func.HttpResponse(
                    "Missing request body parameters (conversation_id, user_msg)",
                    status_code=400
                )
                pass

            logging.info(f"prevmessages:{prevmessages}")
            logging.info("convo_id=%s", convo_id)
            logging.info("user_msg=%s", user_msg)
            logging.info("mute=%s", mute)

            messages = [{"role": 'system', "content": "You're a friend chatbot.  Be nice.  You love dogs."}]

            client = AzureOpenAI(
                azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key= os.environ.get("AZURE_OPENAI_API_KEY"),
                api_version="2023-05-15"
            )
            model = 'keli-35-turbo'

            chat_completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=1,
                top_p=0.5,
            )
            assistant_response_str= chat_completion.choices[0].message.content
            print(f"Response received from OpenAI API: {assistant_response_str}", flush=True)

            temp_dir = tempfile.gettempdir()
            temp_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False)
            print(f"temp_file.name:{temp_file.name}")
            speech_resp = asyncio.run(azure_speech("Hello assistant", temp_file.name))
            print(speech_resp)

        return 'OK'
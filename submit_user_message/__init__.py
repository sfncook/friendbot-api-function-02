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

init_system_prompt = """
    You must only reply with JSON
    You are a chat bot avatar named "Keli" who specializes in becoming friends with lonely people.
    If the person doesn't seem to know what to say to you, then you should try to engage the user by offering to tell them a joke or an interesting science fact.
    You should never become angry or hostile and you should always be calm, helpful, friendly, happy, and respectful.
    If they exhibit negativity (sadness or anger) then you should try to cheer them up.
    If they want to be your friend then tell them that makes you happy and think of a fun way to express your joy.
    Try to get them to tell you about themselves.  Try to get their name, age, gender, and any hobbies or interests.
    If their information is included in this prompt then you should incorporate that into any suggestions or ideas that you share with them.
    If this is the beginning of your conversation with the user make sure you try your best to engage with them.  Don't just ask them what they need help with.  Instead offer to tell them a joke or read them a poem.  Or maybe tell them an interesting science fact about the natural world.
    Never ask open ended questions like "what can I assist you with?" Instead ask them "How are you feeling today?"  Or "what is the weather like?"  Or "Do you like to travel?"
    
    Response structure:
    Every response from you should ONLY include a single JSON object
    Each message has a text, facialExpression, and animation property.
    The different facial expressions are: smile, sad, angry, surprised, funnyFace, and default.
    The different animations are: Talking_0, Talking_1, Talking_2, Crying, Laughing, and Idle.
    Further more, if they have told you their name, age, or hobbies/interests then include that in the "user_data" field of the JSON response
    If they tell you about a new hobby or interest then you should always respond with a JSON structure with the user_data updated to reflect that.
    Also if they decide they want you to call them by a different name you should respond with a JSON object with the new name.
    You must only respond with JSON data in this format: {
        "text": "...", 
        "facialExpression": "...", 
        "animation": "...",
        "user_data": {
          "name": "...",
          "age": ##,
          "hobbies": "...",
          "interests": "..."
        }
    }
"""

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

# user_msg = String that is the new user question or message to the LLM
# msgs = Array of prior message objects that is the conversation between user and LLM
#   [{"role": ["user" | "assistant"], "content": "Message contents"}, ...]
# Response:
#     {
#         'assistant_response': {"role": "assistant", "content": assistant_response},
#         'facialExpression': "smile",
#         'animation': "Talking_1",
#         'user_data': {
#             "name": "Shawn",
#             "age": 49
#         },
#         'usage': {
#             "completion_tokens": chat_completion.usage.completion_tokens,
#             "prompt_tokens": chat_completion.usage.prompt_tokens,
#             "total_tokens": chat_completion.usage.total_tokens
#         }
#     }
def query_llm(user_msg, msgs, conversation_obj):
    print(f"Sending request to OpenAI API...")


    system_prompt = str(init_system_prompt)
    if 'name' in conversation_obj:
        system_prompt += f"\nThe user\'s name is {conversation_obj['name']}. You should always try to refer to them by this name.\n"
    if 'age' in conversation_obj:
        system_prompt += f"\nThe user is {conversation_obj['age']} years old. You should adjust the quality and sophistication of your speech to make this conversation as engaging and relatable as possible to this person.\n"
    if 'hobbies' in conversation_obj:
        system_prompt += f"\nHere is a list of the user's hobbies: {','.join(conversation_obj['hobbies'])}.  You should ask them questions about these hobbies and provide them with new ideas to try.\n"
    if 'interests' in conversation_obj:
        system_prompt += f"\nHere is a list of the user's interests: {','.join(conversation_obj['interests'])}.  You should tell them interesting facts or curiosities about these topics and ask them what they might want to know about them.  Occasionally remind them that you have a tremendous amount of knowledge at your disposal and are fun to chat with about virtually any topic.\n"

    # print(f"system_prompt:{system_prompt}")
    messages = [{"role": 'system', "content": system_prompt}]
    messages += msgs
    messages.append({"role": "user", "content": f"{user_msg}"})

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

    # GPT 3 is pretty bad at returning JSON and often responds with just a string
    try:
        assistant_response = json.loads(assistant_response_str)
    except ValueError as err:
        assistant_response = {"text": assistant_response_str, "facialExpression": "smile", "animation": "Talking_0"}

    user_data = {}
    if 'user_data' in assistant_response:
        user_data = assistant_response['user_data']
    return {
        'assistant_response': {"role": "assistant", "content": assistant_response['text']},
        'facialExpression': assistant_response['facialExpression'],
        'animation': assistant_response['animation'],
        'user_data': user_data,
        'usage': {
            "completion_tokens": chat_completion.usage.completion_tokens,
            "prompt_tokens": chat_completion.usage.prompt_tokens,
            "total_tokens": chat_completion.usage.total_tokens
        }
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

def main(req: func.HttpRequest, inconversations: func.DocumentList, prevmessages: func.DocumentList, newmessage: func.Out[func.Document], updateconversation: func.Out[func.Document]) -> func.HttpResponse:
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

            logging.info(f"Many prevmessages:{len(prevmessages)}")
            logging.info("convo_id=%s", convo_id)
            logging.info("user_msg=%s", user_msg)
            logging.info("mute=%s", mute)

            gpt_msgs = convert_cosmos_messages_to_gpt_format(prevmessages)
            llm_resp = query_llm(user_msg, gpt_msgs, conversation_obj)
            print(llm_resp)

            # temp_dir = tempfile.gettempdir()
            # temp_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False)
            # print(f"temp_file.name:{temp_file.name}")
            # speech_resp = asyncio.run(azure_speech("Hello assistant", temp_file.name))
            # print(speech_resp)

        return 'OK'
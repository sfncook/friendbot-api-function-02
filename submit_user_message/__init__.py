import logging
import azure.functions as func
import uuid
import json
from openai import AzureOpenAI
import os

cors_headers = {
    "Access-Control-Allow-Origin": "*",  # Replace with your allowed origin(s)
    "Access-Control-Allow-Methods": "OPTIONS, POST",  # Add other allowed methods if needed
    "Access-Control-Allow-Headers": "Content-Type",
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

        return 'OK'
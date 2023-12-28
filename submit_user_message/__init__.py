import logging
import azure.functions as func
import json
import asyncio
import tempfile

from .query_llm import query_llm
from .azure_speech import azure_speech, convert_cosmos_messages_to_gpt_format
from .cosmos_data import update_user_data, add_message_to_convo

cors_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "OPTIONS, POST, PUT",
    "Access-Control-Allow-Headers": "Content-Type",
}


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
            print(llm_resp)

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

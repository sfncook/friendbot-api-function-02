import logging
import azure.functions as func
import uuid
import json
import asyncio
import tempfile
from datetime import datetime
from .query_llm import query_llm
from .azure_speech import azure_speech, convert_cosmos_messages_to_gpt_format

cors_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "OPTIONS, POST, PUT",
    "Access-Control-Allow-Headers": "Content-Type",
}

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

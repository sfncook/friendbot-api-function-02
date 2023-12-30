import logging
import azure.functions as func
import uuid
import json
from datetime import datetime

cors_headers = {
    "Access-Control-Allow-Origin": "*",  # Replace with your allowed origin(s)
    "Access-Control-Allow-Methods": "OPTIONS, POST",  # Add other allowed methods if needed
    "Access-Control-Allow-Headers": "Content-Type",
}

def main(req: func.HttpRequest, conversation: func.Out[func.Document]) -> func.HttpResponse:
    method = req.method
    logging.info(f"create_conversation {method}")

    if method == 'OPTIONS':
        return func.HttpResponse(headers=cors_headers)
    else:
        user_name = None
        user_birth_year = None
        user_hobbies = None

        try:
            req_body = req.get_json()
            user_name = req_body.get("user_name")
            user_birth_year = req_body.get("user_birth_year")
            user_hobbies = req_body.get("user_hobbies", [])
        except ValueError:
            pass

        id = str(uuid.uuid4())
        new_conversation = {
            "id": id,
            "user_id": id,
            "user_interests": [],
            "user_hobbies": []
        }

        if user_name is not None:
            new_conversation["user_name"] = user_name

        if user_birth_year is not None:
            new_conversation["user_birth_year"] = user_birth_year
            current_year = datetime.now().year
            new_conversation["user_age"] = current_year - int(user_birth_year)

        if user_hobbies is not None and user_hobbies != []:
            new_conversation["user_hobbies"] = user_hobbies

        conversation.set(func.Document.from_dict(new_conversation))
        return func.HttpResponse(
            status_code=200,
            headers=cors_headers,
            body=json.dumps(new_conversation, separators=(',', ':')),
            mimetype="application/json"
        )
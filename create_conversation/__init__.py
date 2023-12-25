import logging
import azure.functions as func
import uuid
import json

cors_headers = {
    "Access-Control-Allow-Origin": "*",  # Replace with your allowed origin(s)
    "Access-Control-Allow-Methods": "OPTIONS, POST",  # Add other allowed methods if needed
    "Access-Control-Allow-Headers": "Content-Type",
}

def main(req: func.HttpRequest, conversation: func.Out[func.Document]) -> func.HttpResponse:
    id = str(uuid.uuid4())
    new_conversation = {
        "id": id,
        "user_id": id,
        "interests": [],
        "hobbies": []
    }

    conversation.set(func.Document.from_dict(new_conversation))
    return func.HttpResponse(
        status_code=200,
        headers=cors_headers,
        body=json.dumps(new_conversation, separators=(',', ':')),
        mimetype="application/json"
    )
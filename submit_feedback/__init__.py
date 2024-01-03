import logging
import azure.functions as func
import uuid
from datetime import datetime

cors_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "OPTIONS, POST",
    "Access-Control-Allow-Headers": "Content-Type",
}


def main(req: func.HttpRequest, prevmessages: func.DocumentList, newfeedback: func.Out[func.Document]) -> func.HttpResponse:
    method = req.method
    logging.info(f"submit_feedback {method}")

    if method == 'OPTIONS':
        return func.HttpResponse(headers=cors_headers)
    elif method == 'POST':
        try:
            convo_id = req.params.get('convoid')
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                "Missing request body parameters (convoid, request body)",
                status_code=400
            )

        try:
            prev_msg_id = prevmessages[0]["id"]
        except (IndexError, KeyError):
            prev_msg_id = None
        logging.info("convo_id=%s", convo_id)
        logging.info("req_body=%s", req_body)
        logging.info("prev_msg_id=%s", prev_msg_id)

        new_feedback_doc = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": convo_id,
            "prev_msg_id": prev_msg_id,
            "feedback": req_body,
        }
        newfeedback.set(func.Document.from_dict(new_feedback_doc))

        return func.HttpResponse(
            status_code=200,
            headers=cors_headers,
            body='ok',
            mimetype="application/json"
        )
    else:
        logging.info(f"Response: FAILURE")
        return func.HttpResponse("Method not allowed", status_code=405)

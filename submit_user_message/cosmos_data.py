import logging
import uuid
from datetime import datetime
import azure.functions as func


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
    needs_update = False
    for key, value in user_data.items():
        # If the value is a list, handle merging and de-duplication
        if isinstance(value, list):
            if key not in conversation_obj:
                conversation_obj[key] = []

            # Merge with existing list and de-duplicate
            updated_list = list(set(conversation_obj[key] + value))
            if updated_list != conversation_obj[key]:
                conversation_obj[key] = updated_list
                needs_update = True
        # Handle other types of values (like strings not needing splitting)
        elif key not in conversation_obj or conversation_obj[key] != value:
            conversation_obj[key] = value
            needs_update = True

    # Update the item in Cosmos DB if needed
    if needs_update:
        try:
            updateconversation.set(func.Document.from_dict(conversation_obj))
        except Exception as e:
            logging.error(f"Error updating conversation: {e}")

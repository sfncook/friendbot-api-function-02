import azure.functions as func
import json
import uuid

def main(req: func.HttpRequest, document: func.Document, outputDocument: func.Out[func.Document]) -> func.HttpResponse:
    method = req.method

    # GET request - Return a specific document
    if method == 'GET':
        if not document:
            return func.HttpResponse("Document not found", status_code=404)

        document_json = json.dumps(document.to_dict())
        return func.HttpResponse(document_json, mimetype="application/json", status_code=200)

    # POST request - Create a new document
    elif method == 'POST':
        new_document = {
            "id": str(uuid.uuid4()),  # Generate a unique ID for the new document
            # Add other document fields here
        }

        outputDocument.set(func.Document.from_dict(new_document))
        return func.HttpResponse("Document created", status_code=201)

    else:
        return func.HttpResponse("Method not allowed", status_code=405)

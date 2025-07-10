import json
import os
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="delete_vm")
def delete_vm(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    method = req.method  # this will be 'GET', 'POST', etc.

    if method == "GET":
        return func.HttpResponse("Received a GET request", status_code=200)
    elif method == "POST":
        return func.HttpResponse("Received a POST request", status_code=200)
    else:
        return func.HttpResponse(f"Received a {method} request", status_code=200)

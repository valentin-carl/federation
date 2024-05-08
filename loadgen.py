import time
import requests

import choreography.invoke

workflow = {
    "name": "workflow-5001-a",
    #"bucket": "workflow-eimer-2000",
    "bucket": "workflow-bucket-2001",
    "steps": [
        {
            "id": 0,
            "function_name": "check",
            "pre-fetch": {
                "pre-fetches": False,
                "functionInputObjectName": "inputfn1"
            },
            "data": {
                "bucket": "thisisnotaneimer5006",
                "object": "data.pdf"
            },
            "expects_input": True,
            "provider": "tinyFaaS",
            "function_url": "http://34.32.64.15:8000/check"
        },
        {
            "id": 1,
            "function_name": "virus",
            "pre-fetch": {
                "pre-fetches": False,
                "functionInputObjectName": "FUNCTION INPUT OBJECT NAME MUST BE REPLACED BY MIDDLEWARE WHEN PREFETCHING"
            },
            "data": {
                "bucket": "thisisnotaneimer5006",
                "object": "data.pdf"
            },
            "expects_input": True,
            "provider": "google",
            "google_project_id": "workflows-413409"
        },
        {
            "id": 2,
            "function_name": "ocr",
            "pre-fetch": {
                "pre-fetches": False,
                "functionInputObjectName": "FUNCTION INPUT OBJECT NAME MUST BE REPLACED BY MIDDLEWARE WHEN PREFETCHING"
            },
            "data": {
                "bucket": "thisisnotaneimer5006",
                "object": "data.pdf"
            },
            "expects_input": True,
            "provider": "aws",
            "function_url": "https://99cwhykg99.execute-api.us-east-1.amazonaws.com/dev/ocr"
        },
        {
            "id": 3,
            "function_name": "email",
            "pre-fetch": {
                "pre-fetches": False,
                "functionInputObjectName": "FUNCTION INPUT OBJECT NAME MUST BE REPLACED BY MIDDLEWARE WHEN PREFETCHING"
            },
            "data": {
                "bucket": "thisisnotaneimer5006",
                "object": "data.pdf"
            },
            "expects_input": True,
            "provider": "aws",
            "function_url": "https://xj9y3qk6c4.execute-api.us-east-1.amazonaws.com/dev/my-project/email"
        }
    ],
    "credentials": {

    }
}


def send(functionInput: dict):
    # pre-fetching request
    path = choreography.invoke.invoke(
        provider="tinyFaaS",
        workflowStep=workflow["steps"][0],
        workflow=workflow,
        functionInput=None,
        objectName=None,
        pathToPreFetchedData=None
    )
    print(f"got path to pre-fetched data: {path}")
    time.sleep(0.5)
    # invocation request
    choreography.invoke.invoke(
        provider="tinyFaaS",
        workflowStep=workflow["steps"][0],
        workflow=workflow,
        functionInput=functionInput,
        objectName=None,
        pathToPreFetchedData=path
    )


if __name__ == '__main__':

    collectorIp = "34.32.29.225"
    experimentId = "e1_baseline1"  # needs to be valid sqlite table name (no dashes, underscores are find)

    n_minutes = 30
    for i in range(n_minutes*60):
        t = int(time.time() * 1000)
        functionInput = {
            "experiment": {
                "dataCollectorUrl": f"http://{collectorIp}:80/insert",
                "tableName": experimentId,
                "totalExecutionDuration": 0,  # for measuring total execution duration without latency inbetween
                "timeStartMilli": t  # latency between start (client request) and end of workflow @ last function
            },
            # for baseline case
            "input": {
                "bucket": "workflow-eimer-2000",
                "objectName": "data.pdf",
                "aws_access_key_id": "",
                "aws_secret_access_key": ""
            }
        }
        print(f"{int(i/60)}m {i%60}s")
        send(functionInput)
        time.sleep(0.5)

    print("done")


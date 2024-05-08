import choreography.invoke as inv
import choreography.prefetch as pre
import choreography.workflow as wfl

from typing import Any, Dict, Optional, List

import time
import os
import subprocess
import uuid

import boto3
import requests


def userHandler(dataPath, functionInput):
    """
    input structure (this is what happens through invokeAWS in choreography::invoke

    functionInput = {
        "workflow": ...,
        "body": {
            "experiment": {
                "dataCollectorUrl": "...",
                "tableName": "...",
                "totalExecutionDuration": 123,
                "timeStartMilli": 12345
            },
            "input": {}
        }
    }

    for now, assume that the following function can be invoked via HTTP, i.e., it will run only Lambda / tinyFaaS
    """

    # for debugging
    print(functionInput)

    time_start = int(time.time() * 1000)
    print(time_start)

    # extract usable stuff from the input
    # not part of the input
    #functionInput = functionInput["body"]
    #print(f"user handler: functionInput {functionInput}")
    experiment = functionInput["experiment"]
    print(f"user handler: experiment {experiment}")
    functionInput = functionInput["input"]
    print(f"user handler: functionInput {functionInput}")

    # get input parameters
    try:
        filename = functionInput["objectName"]
        bucket = functionInput["bucket"]
        aaki = functionInput["aws_access_key_id"]
        asak = functionInput["aws_secret_access_key"]
        print(f"inputs: {filename}, {bucket}, {aaki}, {asak}")
    except KeyError as e:
        print("error retrieving input parameters: %s", e)
        #return {"statusCode": 400, "body": "missing input parameters filename or bucket"}

    try:
        # download pdf from s3
        s3 = boto3.client(
            service_name="s3",
            aws_access_key_id=aaki,
            aws_secret_access_key=asak
        )
        with open("/tmp/file.pdf", "wb") as f:
            s3.download_fileobj(
                bucket,
                filename,
                f
            )
        print("stored file in tmp dir")

        ret = subprocess.run(["ocrmypdf", "/tmp/file.pdf", "/tmp/out.pdf", "--use-threads", "--force-ocr", "--output-type", "pdf"], capture_output=True, text=True)

        print({"stdout": ret.stdout, "stderr": ret.stderr})
        print(os.listdir("/tmp"))

        # upload to s3
        for file in os.listdir("/tmp"):
            print(file)
            if os.path.isdir(f"/tmp/{file}"):
                print(os.listdir(f"/tmp/{file}"))
                for f in os.listdir(f"/tmp/{file}"):
                    with open(f"/tmp/{file}/{f}", "rb") as f:
                        s3.put_object(
                            Bucket=bucket,
                            Key=f"ocr_{file}_{f}",
                            Body=f
                        )
            else:
                with open(f"/tmp/{file}", "rb") as f:
                    s3.put_object(
                        Bucket=bucket,
                        Key=f"ocr_{file}.pdf",
                        Body=f
                    )
    except Exception as e:
        print(e)
        print("exception while trying to do ocr or uploading ocr'd pdf to s3")

    # update total workflow duration
    time_end = int(time.time()*1000)
    td: int = time_end - time_start
    print(f"total time for this function only: {td}")
    ted = experiment["totalExecutionDuration"]
    if ted is None:
        print("setting totalExecutionDuration to 0")
        ted = 0
    ted += td
    print(f"current totalExecutionDuration {ted}")

    fI = {
        "experiment": {
            "dataCollectorUrl": experiment["dataCollectorUrl"],
            "tableName": experiment["tableName"],
            "totalExecutionDuration": ted,
            "timeStartMilli": experiment["timeStartMilli"]
        },
        "input": functionInput
    }

    return fI


def handler(functionInput, ctx) -> Dict:
    # taken from the aws wrapper and adjusted to fit the custom container model

    # ---
    print(f"functionInput {functionInput}")
    # ---

    event = functionInput
    print(f"EVENT {event}")

    import json
    #body = json.loads(event["body"])
    body = event["body"]

    # setting parameters relevant for workflows
    functionInput, workflow = body["body"], body["workflow"]
    currentStep, nextStep = wfl.getCurrentStep(workflow), wfl.getNextStep(workflow)  # TODO handle cases in which currentStep is None!!!
    updatedWorkflow = wfl.updateWorkflow(workflow)
    credentials = workflow.get("credentials").get("aws")
    assert credentials is not None
    s3 = boto3.client(
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        service_name="s3"
    )

    # FIXME rename to pre-fetch.functionInputObjectName ... (here and later on; and in google wrapper ...)
    # TODO check this uses the most up to date version of workflow.json

    # 2 invoke the next function early if it pre-fetches
    nextStepPreFetches = nextStep is not None and nextStep.get("pre-fetch").get("pre-fetches")
    print(f"next step pre-fetches = {nextStepPreFetches}")
    nextObjectName = str(uuid.uuid4())[:32]
    preFetchedDataPath = None
    nextProvider = None
    if nextStepPreFetches:
        # if the next step doesn't run on tinyFaaS, it will wait for an input to appear in the workflow bucket
        # the object will have the name `nextObjectName`
        # the next step will look for this name in `currentStep->pre-fetch->functionInputObjectName`
        nextStep["pre-fetch"]["functionInputObjectName"] = nextObjectName
        updatedSteps = updatedWorkflow["steps"]
        for i in range(len(updatedSteps)):
            if updatedSteps[i]["id"] == nextStep["id"]:
                updatedWorkflow["steps"][i] = nextStep
                break

        print(f"updatedWorkflow {updatedWorkflow}")

        nextProvider = nextStep.get("provider")
        assert nextProvider is not None

        preFetchedDataPath = inv.invoke(  # will be None if not tinyFaaS
            provider=nextProvider,
            workflowStep=nextStep,
            workflow=updatedWorkflow,
            functionInput=None,
            objectName=nextObjectName,  # the name of the object in the workflow bucket where the function inputs for the next step will be stored
            pathToPreFetchedData=None   # this parameter is used for tinyFaaS invocation requests only
        )

    # 3 if this function pre-fetches, get the data & function args
    currentStepPreFetches = currentStep is not None and currentStep["pre-fetch"]["pre-fetches"]
    print(f"current step pre-fetches = {currentStepPreFetches}")
    functionInputObjectName = None
    dataPath = None
    if currentStepPreFetches:
        dataPath = pre.prefetch(s3, currentStep)
        print(f"stored data under {dataPath}")
        if currentStep.get("expects_input"):
            print("current step expects input, trying to get it")
            functionInputObjectName = currentStep.get("pre-fetch").get("functionInputObjectName")
            print(f"currentStep {currentStep}")
            print(f"functionInputObjectName {functionInputObjectName}")
            functionInput = pre.getFunctionInput(s3, workflow.get("bucket"), functionInputObjectName)
            print(f"(pre-fetching) got function input {functionInput}")

    # 4 call the user function
    print("calling handler")
    result = userHandler(dataPath, functionInput)
    print(f"called handler, got result {result}")

    # 5/6 pass args to next function (or send an invocation request in the case of tinyFaaS)
    # or invoke the next function directly
    if nextStep is not None:
        # pass function args via s3 if the next functions was already invoked and expects inputs
        # tinyFaaS invocation request
        if nextStepPreFetches and nextProvider.lower() == "tinyfaas":
            # inv.sendTinyfaasInvocationRequest(
            #     workflow=updatedWorkflow,
            #     workflowStep=nextStep,
            #     preFetchedDataPath=preFetchedDataPath,
            #     functionInput=result
            # )
            _ = inv.invoke(
                provider=nextProvider,
                workflowStep=nextStep,
                workflow=updatedWorkflow,
                functionInput=result,
                objectName=nextObjectName,
                pathToPreFetchedData=preFetchedDataPath
            )
        # next function is already running and just waiting for the function input in the workflow bucket
        elif nextStepPreFetches and nextStep.get("expects_input") and nextProvider.lower() != "tinyfaas":
            assert result, "function handler returned None but next step expects an input"
            pre.putFunctionInput(
                s3=s3,
                bucketName=workflow.get("bucket"),
                objectName=nextObjectName,
                args=result
            )
        # if the next function doesn't pre-fetch, call it now => it hasn't been invoked yet
        else:
            _ = inv.invoke(
                provider=nextStep.get("provider"),
                workflowStep=nextStep,
                workflow=updatedWorkflow,
                functionInput=result,
                objectName=None,
                pathToPreFetchedData=None  # not required if tinyFaaS function doesn't pre-fetch any data
            )

    return {
        "status_code": 200
    }

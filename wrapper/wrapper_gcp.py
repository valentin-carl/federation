import choreography.invoke as inv
import choreography.prefetch as pre
import choreography.workflow as wfl

# user function is in
# aws: main.py
# gcp: user_main.py
# tinyFaaS: main.py
import user_main # this is supposed to be underlined in red during development

from typing import Any, Dict, Optional
import uuid, json, base64

import boto3
import functions_framework # TODO install it first and add automatically to requirements


# TODO check that handler is set correctly in serverless.yml
#  -> it is but does it matter what I put in the deployment.json?
# `cloud_event` has the type cloudevents.http.event.CloudEvent
# I put `Any` because I don't want to import that just for the type annotation
@functions_framework.cloud_event
def wrapper_gcp(cloud_event: Any):

    # TODO test
    # - [ ] test

    # cloud_event.data = {
    #   "body": ...,
    #   "workflow": ...,
    # }

    # 1 update workflow: remove the current step
    # 2 call the next step if it pre-fetches data => in that case pass args to it later
    # 3 if the current step pre-fetches, download data & get function inputs (if the function takes any)
    # 4 call the function handler
    # 5 upload function input if next function pre-fetches
    # 6 if it doesn't pre-fetch, call it now

    # setting parameters relevant for workflows

    print(f"cloud event type {type(cloud_event)}")

    dataEncoded: bytes = cloud_event.data["message"]["data"]

    data = json.loads(base64.b64decode(dataEncoded).decode("utf-8"))

    functionInput = data.get("body")
    workflow      = data.get("workflow")

    currentStep     = wfl.getCurrentStep(workflow)
    nextStep        = wfl.getNextStep(workflow)
    updatedWorkflow = wfl.updateWorkflow(workflow)

    credentialsAws = workflow.get("credentials").get("aws")
    assert credentialsAws is not None
    s3 = boto3.client(
        aws_access_key_id=credentialsAws["aws_access_key_id"],
        aws_secret_access_key=credentialsAws["aws_secret_access_key"],
        service_name="s3"
    )

    # 2 invoke the next function early if it pre-fetches
    nextStepPreFetches = nextStep is not None and nextStep["pre-fetch"]["pre-fetches"]
    print(f"next step pre-fetches = {nextStepPreFetches}")
    nextObjectName = str(uuid.uuid4())[:32]
    if nextStepPreFetches:
        nextProvider: str = nextStep.get("provider")
        assert nextProvider is not None

        # if the next step doesn't run on tinyFaaS, it will wait for an input to appear in the workflow bucket
        # the object will have the name `nextObjectName`
        # the next step will look for this name in `currentStep->pre-fetch->functionInputObjectName`
        # TODO do the same in tinyfaas_invocation_request::poke()
        nextStep["pre-fetch"]["functionInputObjectName"] = nextObjectName
        updatedSteps = updatedWorkflow["steps"]
        for i in range(len(updatedSteps)):
            if updatedSteps[i]["id"] == nextStep["id"]:
                updatedWorkflow["steps"][i] = nextStep
                break

        preFetchedDataPath = inv.invoke(
            provider=nextProvider,
            workflowStep=nextStep,
            workflow=updatedWorkflow,
            functionInput=None,
            objectName=nextObjectName,  # functionInputObjectName for next step => this is where the args will be stored
            pathToPreFetchedData=None   # this is for tinyFaaS invocation requests only
        )

    # 3 if this function pre-fetches, get the data & function args
    currentStepPreFetches = currentStep is not None and currentStep["pre-fetch"]["pre-fetches"]
    print(f"current step pre-fetches = {currentStepPreFetches}")
    functionInputObjectName, dataPath = None, None
    if currentStepPreFetches:
        functionInputObjectName = currentStep["pre-fetch"]["functionInputObjectName"]
        dataPath = pre.prefetch(s3, currentStep)
        if currentStep.get("expects_input"):
            print("current step expects input, trying to get it")
            # TODO should this function also remove the object from s3?
            functionInput = pre.getFunctionInput(s3, workflow["bucket"], functionInputObjectName)

    # 4 call the user function
    result: Optional = user_main.handler(dataPath, functionInput)
    print(f"user function handler result: {result}")

    # 5/6 pass arguments to next function (invocation request for tinyFaaS)
    # or invoke the next function if it's not pre-fetching
    if nextStep is not None:
        # tinyFaaS invocation request
        if nextStepPreFetches and nextProvider.lower() == "tinyfaas":
            _ = inv.invoke(
                provider=nextStep["provider"],
                workflowStep=nextStep,
                workflow=updatedWorkflow,
                functionInput=result,
                objectName=nextObjectName,
                pathToPreFetchedData=preFetchedDataPath
            )
        # next function is already running and waiting for input coming from workflow bucket in s3
        elif nextStepPreFetches and nextStep.get("expects_input") and nextProvider.lower() != "tinyfaas":
            assert result, "function handler returned None but next step expects an input"
            pre.putFunctionInput(s3, workflow["bucket"], nextObjectName, result)
        # next function didn't pre-fetch anything => wasn't invoked yet => call it now
        else:
            _ = inv.invoke(
                provider=nextStep["provider"],
                workflowStep=nextStep,
                workflow=updatedWorkflow,
                functionInput=result,
                objectName=None,
                pathToPreFetchedData=None
            )

    return {
        "status_code": 200
    }

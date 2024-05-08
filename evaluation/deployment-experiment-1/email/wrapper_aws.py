import choreography.invoke as inv
import choreography.prefetch as pre
import choreography.workflow as wfl

# user function is in
# aws: main.py
# gcp: user_main.py
# tinyFaaS: main.py
import main

from typing import Any, Dict, Optional
import uuid

import boto3


def wrapper_aws(event: Dict, context: Any) -> Dict:
    """
    event = {
      "body": ...,
      "workflow": ...,
      "pre-fetch": {
          "pre-fetches": True,
          "functionInputObjectName": "my-object-123"
      }
    }

    1 update workflow: remove the current step
    2 call the next step if it pre-fetches data => in that case pass args to it later
    3 if the current step pre-fetches, download data & get function inputs (if the function takes any)
    4 call the function handler
    5 upload function input if next function pre-fetches
    6 if it doesn't pre-fetch, call it now
    """

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

        nextProvider = nextStep.get("provider")
        assert nextProvider is not None

        preFetchedDataPath = inv.invoke(  # will be None if not tinyFaaS
            provider=nextProvider,
            workflowStep=nextStep,
            workflow=updatedWorkflow,
            functionInput=None,
            objectName=nextObjectName, # the name of the object in the workflow bucket where the function inputs for the next step will be stored
            pathToPreFetchedData=None  # this parameter is used for tinyFaaS invocation requests only
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
            functionInputObjectName = currentStep.get("pre-fetch").get(
                "functionInputObjectName")
            functionInput = pre.getFunctionInput(s3, workflow.get("bucket"), functionInputObjectName)
            print(f"(pre-fetching) got function input {functionInput}")

    # 4 call the user function
    print("calling handler")
    result = main.handler(dataPath, functionInput)
    print(f"called handler, got result {result}")

    # 5/6 pass args to next function (or send an invocation request in the case of tinyFaaS)
    # or invoke the next function directly
    if nextStep is not None:

        # pass function args via s3 if the next functions was already invoked and expects inputs
        # TODO this could have to be a tinyFaaS invocation request, add that!!! (& test)
        # TODO just use invoke?

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

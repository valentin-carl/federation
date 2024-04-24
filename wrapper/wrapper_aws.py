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


# AWS entrypoint
# TODO list this function as handler in `serverless.yml`
def handlerAws(event: Dict, context: Any) -> Dict:
    # TODO test
    # - [ ] test

    # event = {
    #   "body": ...,
    #   "workflow": ...,
    #   "pre-fetch": {
    #       "objectName": "my-object-123"
    #   }
    # }

    # TODO adjust for tinyFaaS native pre-fetching requests
    # 1 update workflow: remove the current step
    # 2 call the next step if it pre-fetches data => in that case pass args to it later
    # 3 if the current step pre-fetches, download data & get function inputs (if the function takes any)
    # 4 call the function handler
    # 5 upload function input if next function pre-fetches
    # 6 if it doesn't pre-fetch, call it now

    # setting parameters relevant for workflows
    functionInput, workflow = event["body"], event["workflow"]
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
    nextObjectName, preFetchedDataPath = None, None
    if nextStepPreFetches:
        nextObjectName = str(uuid.uuid4())[:32]

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
            objectName=nextObjectName,
            pathToPreFetchedData=None  # for tinyFaaS invocation requests only
        )

    # 3 if this function pre-fetches, get the data & function args
    functionInputObjectName, dataPath = None, None
    if currentStep.get("pre-fetch") is not None and currentStep.get("pre-fetch").get("pre-fetches"):

        functionInputObjectName = currentStep.get("pre-fetch").get("functionInputObjectName")  # will stay None if this step pre-fetches
        dataPath = pre.prefetch(s3, currentStep)
        print(f"stored data under {dataPath}")
        if currentStep.get("expects_input"):
            functionInput = pre.getFunctionInput(s3, workflow.get("bucket"), functionInputObjectName)

    # call the user function
    print("calling handler")
    result = main.handler(dataPath, functionInput)
    print("called handler")

    if nextStep is not None:

        # pass function args via s3 if the next functions was already invoked and expects inputs
        # TODO this could have to be a tinyFaaS invocation request, add that!!! (& test)
        # TODO just use invoke?

        if nextStepPreFetches and nextProvider.lower() == "tinyfaas":
            inv.sendTinyfaasInvocationRequest(
                workflow=updatedWorkflow,
                workflowStep=nextStep,
                preFetchedDataPath=preFetchedDataPath,
                functionInput=result
            )

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
            inv.invoke(
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

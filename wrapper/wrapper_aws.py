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
    currentStep, nextStep = wfl.getNextStep(workflow), wfl.getNextStep(workflow)
    updatedWorkflow = wfl.updateWorkflow(workflow)
    credentials = workflow.get("credentials").get("aws")
    assert credentials is not None
    s3 = boto3.client(
        aws_access_key_id=credentials["aws"]["aws_access_key_id"],
        aws_secret_access_key=credentials["aws"]["aws_secret_access_key"],
        service_name="s3"
    )
    objectName = None
    if currentStep.get("pre-fetch") is not None:
        assert currentStep.get("pre-fetch").get("objectName") != ""
        objectName = currentStep.get("pre-fetch").get("objectName")

    # invoke the next function early if it pre-fetches
    nextStepPreFetches = nextStep is not None and nextStep.get("pre-fetch")
    nextObjectName = str(uuid.uuid4())[:32]
    if nextStepPreFetches:
        nextProvider = nextStep.get("provider")
        assert nextProvider is not None
        inv.invoke(
            provider=nextProvider,
            workflowStep=nextStep,
            workflow=updatedWorkflow,
            functionInput=None,
            objectName=nextObjectName,
        )

    # if this function pre-fetches, get the data & function args
    dataPath = None
    if currentStep.get("pre-fetch"):
        dataPath = pre.prefetch(s3, currentStep)
    if currentStep.get("expects_input"): # if this is true, `pre-fetch` should also be False
        # TODO should this function also remove the object from s3?
        functionInput = pre.getFunctionInput(s3, workflow.get("bucket"), objectName)

    # call the user function
    # @user: please don't write functions that return None >.<
    result = main.handler(dataPath, functionInput)

    # pass function args via s3 if the next functions was already invoked and expects inputs
    if nextStep is not None and nextStepPreFetches and nextStep.get("expects_input"):
        pre.putFunctionInput(
            s3=s3,
            bucketName=workflow.get("bucket"),
            objectName=nextObjectName,
            args=result # TODO check this is correct and we don't need any of that workflow stuff
        )
    # if the next function doesn't pre-fetch, call it now => it hasn't been invoked yet
    else:
        # TODO check
        #  => should be fine but is yet to be tested
        inv.invoke(
            provider=nextStep.get("provider"),
            workflowStep=nextStep,
            workflow=updatedWorkflow,
            args=result,
            objectName=None
        )

    return {
        "status_code": 200
    }

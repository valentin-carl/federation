import uuid
from typing import Dict, Any, Optional

import boto3

# TODO remove the choreography module from wrapper (just for lsp to help now) => imports will stay the same
import choreography.workflow as wfl
import choreography.invoke as inv
import choreography.prefetch as pre


from main import handler


# if there is a next step:
# -> tinyFaaS: sends prefetching request
# -> other: invokes the function to start downloading early
def poke(inputDict: Dict[str, Any], updatedWorkflow: Dict[str, Any]) -> (str, str):
    nextStep = wfl.getNextStep(inputDict.get("workflow"))
    nextPfdp, objectName = None, None
    if nextStep is None:
        return "", ""
    if nextStep.get("pre-fetch").get("pre-fetches"):
        print("next step pre-fetches")
        if nextStep.get("expects-input"):
            # name of the object that will hold the inputs for the next function (if it runs on aws or gcp)
            objectName = f"{nextStep.get('function_name')}-{str(uuid.uuid4())[:32]}"
            # TODO add this to nextStep->pre-fetches->nextFunctionInputObjectName
        nextPfdp = inv.invoke(
            provider=nextStep.get("provider"),
            workflowStep=nextStep,
            workflow=updatedWorkflow,
            functionInput=None,
            objectName=objectName,
            pathToPreFetchedData=None
        )
    return nextPfdp, objectName


def invokeHandler(inputDict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    preFetchedDataPath = inputDict.get("preFetchedDataPath")
    functionInput = inputDict.get("functionInput")
    # actual function invocation
    nextStepFunctionInput = handler(preFetchedDataPath, functionInput)
    return nextStepFunctionInput


def handleInvocationRequest(inputDict: Dict[str, Any]) -> int:
    """
    inputDict is expected to have the following structure

    {
        "workflow": {
            "name": "...",
            "bucket": "...",
            "steps": { },
            "credentials": { }
        },
        //"functionInputObjectName": "...", => not for tinyFaaS!!!
        "functionInput": { ... }, => this instead (only for tf)
        "preFetchedDataPath": "..."
    }
    """

    # update workflow for next step
    updatedWorkflow = wfl.updateWorkflow(inputDict.get("workflow"))
    print("updated workflow")
    print(updatedWorkflow)

    # poke if next function pre-fetches
    # `nextPfdp` is a path that the invocationRequest of tinyFaaS expects
    # it's None for any other provider => for other providers, there's just one function call,
    # and it already knows the path it stores the pre-fetched data under
    print("trying to poke next function")
    nextPfdp, nextFion = poke(inputDict, updatedWorkflow)

    # invoke handler
    print("invoking function handler")
    nextStepFunctionInput = invokeHandler(inputDict)

    s3 = boto3.client(
        aws_access_key_id=inputDict.get("workflow").get("credentials").get("aws_access_key_id"),
        aws_secret_access_key=inputDict.get("workflow").get("credentials").get("aws_secret_access_key"),
        service_name="s3"
    )
    nextStep = wfl.getNextStep(inputDict.get("workflow"))
    if nextStep is None:
        print("no next step in workflow")
        return 200

    if nextStep.get("pre-fetch").get("pre-fetches") and nextStep.get("expects_input"):
        print("next step pre-fetches and expects an input, upload args to s3 workflow bucket")
        pre.putFunctionInput(
            s3=s3,
            bucketName=inputDict.get("workflow").get("bucket"),
            objectName=nextFion,
            args=nextStepFunctionInput
        )

    # invoke the next function if it has been invoked yet (i.e., if it doesn't pre-fetch)
    else:
        print("next step doesn't pre-fetch, invoking it just now")
        inv.invoke(
            nextStep.get("provider"),
            workflowStep=nextStep,
            #workflow=inputDict.get("workflow"),
            workflow=updatedWorkflow,
            functionInput=nextStepFunctionInput,
            objectName=None,
            pathToPreFetchedData=nextPfdp,
        )

    return 200

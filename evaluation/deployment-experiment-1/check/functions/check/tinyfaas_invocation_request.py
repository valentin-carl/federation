import uuid
from typing import Dict, Any, Optional

import boto3

import workflow as wfl
import invoke as inv
import prefetch as pre


from main import handler


def addFionToNextStep(updatedWorkflow, functionInputObjectName):
    nextStep = wfl.getCurrentStep(updatedWorkflow)
    print(f"nextStep {nextStep}")
    nextStep["pre-fetch"]["functionInputObjectName"] = functionInputObjectName
    print(f"nextStep {nextStep}")
    updatedWorkflow["steps"][0] = nextStep
    print(f"updatedWorkflow {updatedWorkflow}")
    return updatedWorkflow


# if there is a next step:
# -> tinyFaaS: sends prefetching request
# -> other: invokes the function to start downloading early
def poke(inputDict: Dict[str, Any], updatedWorkflow: Dict[str, Any]) -> (str, str):
    print(f"poking next function with input dict {inputDict}")
    print(f"sending updated workflow {updatedWorkflow}")
    nextStep = wfl.getNextStep(inputDict.get("workflow"))
    print(f"got next step {nextStep}")
    nextPfdp, objectName = None, None
    if nextStep is None:
        print("next step is none")
        return "", ""
    if nextStep.get("pre-fetch").get("pre-fetches"):
        print("next step pre-fetches")
        print(f"nextStep {nextStep}")
        if nextStep.get("expects_input"):
            print("next step expects input")
            # name of the object that will hold the inputs for the next function (if it runs on aws or gcp)
            objectName = f"{nextStep.get('function_name')}-{str(uuid.uuid4())[:32]}"
            # TODO add this to nextStep->pre-fetches->nextFunctionInputObjectName
            # TODO check and add this to all other functions as well
            updatedWorkflow = addFionToNextStep(updatedWorkflow, objectName)

            print()
            print(f"storing inputs for next function as object {objectName}")
            print()

        try:
            nextPfdp = inv.invoke(
                provider=nextStep.get("provider"),
                workflowStep=nextStep,
                workflow=updatedWorkflow,  # TODO this workflow is needs the updated functionInputObjectName for the next step
                functionInput=None,
                objectName=objectName,
                pathToPreFetchedData=None
            )
        except Exception as e:
            print("error while trying to invoke next function")
            print(e)
        print(f"invoked next function as poke, got nextPfdp {nextPfdp}")
        print(f"object name has the value {objectName}")
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

    print("handling invocation request")
    print(f"got input for invocation request: {inputDict}")

    # update workflow for next step
    updatedWorkflow = wfl.updateWorkflow(inputDict.get("workflow"))
    print("updated workflow")
    print(updatedWorkflow)

    # poke if next function pre-fetches
    # `nextPfdp` is a path that the invocationRequest of tinyFaaS expects
    # it's None for any other provider => for other providers, there's just one function call,
    # and it already knows the path it stores the pre-fetched data under
    print("trying to poke next function")
    try:
        nextPfdp, nextFion = poke(inputDict, updatedWorkflow)
        print(f"poke result {nextPfdp}, {nextFion}")
    except:
        print("error while trying to poke next function")

    # TODO add nextFion to workflow
    # will crash if nextFion is None
    updatedWorkflow = addFionToNextStep(updatedWorkflow, nextFion)

    # invoke handler
    try:
        print("invoking function handler")
        nextStepFunctionInput = invokeHandler(inputDict)
        print(f"input for next function will be {nextStepFunctionInput}")
    except Exception as e:
        print(e)
        print("user handler failed and caused exception")

    s3 = boto3.client(
        aws_access_key_id=inputDict.get("workflow").get("credentials").get("aws").get("aws_access_key_id"),
        aws_secret_access_key=inputDict.get("workflow").get("credentials").get("aws").get("aws_secret_access_key"),
        service_name="s3"
    )
    nextStep = wfl.getNextStep(inputDict.get("workflow"))
    if nextStep is None:
        print("no next step in workflow")
        return 200
    else:
        print("next step isn't none")

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
            workflow=updatedWorkflow,
            functionInput=nextStepFunctionInput,
            objectName=None,
            pathToPreFetchedData=nextPfdp,
        )

    return 200

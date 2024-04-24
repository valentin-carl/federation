import requests, json

from typing import Dict, Any, Optional
from google.cloud import pubsub_v1
from google.oauth2 import service_account


def invoke(
        provider: str,
        workflowStep: Dict[str, Any],
        workflow: Optional[Dict[str, Any]],
        functionInput: Optional[Dict[str, Any]],
        objectName: Optional[str],  # functionInputObjectName
        pathToPreFetchedData: Optional[str]
) -> Optional[str]:

    if workflowStep is None or workflowStep == {}:
        print("no workflow step to invoke")
        return None

    # amazon
    if provider.lower() == "aws":
        invokeAWS(workflowStep, workflow, functionInput, objectName)

    # google
    elif provider.lower() == "gcp" or provider.lower() == "google":
        invokeGCP(
            projectId=workflowStep.get("google_project_id"),
            credentials=workflow.get("credentials").get("google"),
            topic=workflowStep.get("function_name").lower(), # TODO brauch ich das .lower()?
            args={
                "body": ("" if functionInput is None else functionInput),
                "workflow": ("" if workflow is None else workflow)
                # TODO make sure nothing broke from deleting the objectName thing
            }
        )

    # tinyFaaS
    elif provider.lower() == "tinyfaas":
        pfr = pathToPreFetchedData is None
        if pfr:
            return sendTinyfaasPrefetchingRequest(workflow, workflowStep)
        else:
            sendTinyfaasInvocationRequest(workflow, workflowStep, pathToPreFetchedData, functionInput)

    # error
    else:
        raise Exception("unknown provider, cannot invoke")

    return None

def invokeAWS(
        workflowStep: Dict[str, Any],
        workflow: Optional[Dict[str, Any]],
        functionInput: Optional[Dict[str, Any]],
        objectName: Optional[str]
) -> None:
    # http request
    # can be used for both starting a workflow early and normal function calls with arguments (prefetching vs non-prefetching requests)
    if workflowStep:
        print("invoking next step of workflow")
        result = requests.post(
            url=workflowStep["function_url"],
            json={
                "workflow": ("" if workflow is None else workflow),
                "body": ("" if functionInput is None else functionInput),
                "objectName": ("" if objectName is None else objectName)  # TODO necessary??????? => should not be used anymore and added to the workflow steps list instead, but check everything is adjusted before deleting it
            }
        )
        print(f"result of invoking workflow: {result}")
    else:
        print("no next step to invoke--finished workflow")


def invokeGCP(projectId: str, credentials: Dict[str, Any], topic: str, args: Dict[str, Any]) -> str:
    # pub sub
    # topic == function name
    # => deployer has to create topics in advance => sls deploy does that
    publisher = pubsub_v1.PublisherClient(credentials=service_account.Credentials.from_service_account_info(credentials))
    topicPath = publisher.topic_path(projectId, topic)
    data = json.dumps(args).encode("utf-8")  # TODO does this contain all necessary workflow information?
    print(data)
    return publisher.publish(topicPath, data).result()


def sendTinyfaasPrefetchingRequest(workflow: Dict[str, Any], workflowStep: Dict[str, Any]) -> str:
    """
    tinyFaaS expects:
    - credentialsAws
    - data: { bucket, object }
    - pf-request
    """
    url = workflowStep.get("function_url")
    payload = {
        "pf-request": True,
        "credentials": workflow.get("credentials").get("aws"),
        "data": workflowStep.get("data")
    }
    result = requests.post(url=url, json=payload)
    preFetchedDataPath = result.text
    return preFetchedDataPath


def sendTinyfaasInvocationRequest(workflow: Dict[str, Any], workflowStep: Dict[str, Any], preFetchedDataPath: str, functionInput: Dict[str, Any]) -> None:
    """
    tinyFaaS expects:
    - workflow
    - preFetchedDataPath
    - functionInput
    """
    url = workflowStep.get("function_url")
    payload = {
        "workflow": workflow,
        "preFetchedDataPath": preFetchedDataPath,
        "functionInput": functionInput
    }
    result = requests.post(url=url, json=payload)
    assert result.status_code == 200

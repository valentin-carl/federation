import boto3, requests, json

from typing import Dict, Any, Optional
from google.cloud import pubsub_v1


def invoke(provider: str,
           workflowStep: Dict[str, Any],
           workflow: Optional[Dict[str, Any]],
           functionInput: Optional[Dict[str, Any]],
           # if the next function pre-fetches, tell it which object name to look for in s3 for the function args
           objectName: Optional[str]
           ) -> None:
    if provider.lower() == "aws":
        invokeAWS(workflowStep, workflow, functionInput, objectName)
    elif provider.lower() == "gcp" or provider.lower() == "google":
        invokeGCP(
            projectId=workflowStep.get("google_project_id"),
            credentials=workflow.get("credentials").get("google"), # TODO check this is right
            topic=workflowStep.get("function_name").lower(), # TODO make sure the topic is correct
            args={
                "body": ("" if functionInput is None else functionInput),
                "workflow": ("" if workflow is None else workflow),
                "objectName": ("" if objectName is None else objectName)
        })
    elif provider.lower() == "tinyfaas":
        # TODO
        invokeTinyFaaS()
    else:
        raise Exception("unknown provider, cannot invoke")

def invokeAWS(
        workflowStep: Dict[str, Any],
        workflow: Optional[Dict[str, Any]],
        functionInput: Optional[Dict[str, Any]],
        objectName: Optional[str]
) -> None:
    # http request
    # can be used for both starting a workflow early and normal function calls with arguments
    # TODO check this is actually true
    if workflowStep:
        print("invoking next step of workflow")
        result = requests.post(
            url=workflowStep["functionUrl"],
            json={
                "workflow": ("" if workflow is None else workflow),
                "body": ("" if functionInput is None else functionInput),
                "objectName": ("" if objectName is None else objectName)
            }
        )
        print(f"result of invoking workflow: {result}")
    else:
        print("no next step to invoke--finished workflow")

def invokeGCP(projectId: str, credentials: Dict[str, Any], topic: str, args: Dict[str, Any]) -> str:
    # pub sub
    # topic == function name
    # => deployer has to create topics in advance => sls deploy does that
    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    topicPath = publisher.topic_path(projectId, topic)
    data = json.dumps(args).encode("utf-8")
    print(data)
    return publisher.publish(topicPath, data).result()

def invokeTinyFaaS():
    # http/pre-fetching request for tinyFaaS
    # TODO
    # this function should also handle non-pre-fetching requests
    pass

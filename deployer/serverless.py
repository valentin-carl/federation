import utils.utils
from typing import Dict, Optional, Any


def generateAWS(deployment: Dict[str, Any], functionName: str) -> Optional[str]:
    # - [x] test
    # => works!
    serverless = deployment["serverless"]
    function   = deployment["functions"][functionName]
    provider   = deployment["providers"]["aws"]
    try:
        yaml = utils.utils.generateYaml({
            "app": serverless["app"],
            "frameworkVersion": 3,
            "service": f"{functionName}-service",
            "org": serverless["org"],
            "functions": {
                functionName: {
                    "handler": function["handler"], # TODO adjust
                    "url": True,
                    "events": [
                        {
                            "http": {
                                "path": f"{serverless['project']}/{functionName}",
                                "async": True,
                                "method": function["method"]
                            }
                        }
                    ]
                }
            },
            "provider": {
                "name": "aws",
                "timeout": 180,
                "runtime": "python3.10",
                "architecture": "arm64",
                "region": function["region"]
            }
        })
        return yaml
    except Exception as e:
        print(e)
        print(f"exception occurred while trying to create serverless configuration for AWS lambda function {functionName}")
        return None

def generateGCP(deployment: Dict[str, Any], functionName: str) -> Optional[str]:
    # - [x] test
    # => works!
    # side note: the function name cannot contain the string "goog"
    serverless = deployment["serverless"]
    function   = deployment["functions"][functionName]
    provider   = deployment["providers"]["google"]
    try:
        yaml = utils.utils.generateYaml({
            "frameworkVersion": 3,
            "service": f"{functionName}-service".lower(),
            "plugins": [
                "serverless-google-cloudfunctions"
            ],
            "functions": {
                functionName: {
                    "handler": "wrapper_gcp", # TODO adjust
                    "events": [
                        {
                            "event": {
                                "eventType": "providers/cloud.pubsub/eventTypes/topic.publish",
                                "resource": "projects/${self:provider.project, \"\"}/topics/" + functionName.lower()
                            }
                        }
                    ]
                }
            },
            "provider": {
                "name": "google",
                "project": provider["project"],
                "runtime": "python39"
            }
        })
        return yaml
    except Exception as e:
        print(e)
        print(f"exception occurred while trying to create serverless configuration for google cloud function {functionName}")
        return None

def generateTinyFaas(deployment: Dict[str, Any], functionName: str) -> Optional[str]:
    serverless = deployment["serverless"]
    function   = deployment["functions"][functionName]
    provider   = deployment["providers"]["tinyFaaS"] # TODO panic
    try:
        yaml = utils.utils.generateYaml({
            "custom": {
                "tinyfaas": {
                    "functions": [
                        {
                            "name": functionName,
                            "env": "python3",
                            "threads": function["tinyFaaSOptions"]["threads"],
                            "source": f"./functions/{functionName}",
                            "deployTo": [
                                {
                                    "name": "tf-node-0"
                                }
                            ]
                        }
                    ],
                    "nodes": provider["nodes"]
                }
            },
            "plugins": [
                "serverless-tinyfaas"
            ],
            # note: provider & service are required for serverless to be happy,
            # but they don't mean anything for tinyfaas
            "provider": {
                "name": "aws"
            },
            "service": f"{functionName}-service"
        })
        return yaml
    except Exception as e:
        print(e)
        print(f"exception occurred while trying to create serverless configuration for tinyFaaS function {functionName}")
        return None

def generateSlsCompose(deployment: Dict[str, Any]) -> Optional[str]:
    functions = deployment["functions"]
    try:
        compose = {
            "services": {}
        }
        for fn in functions:
            compose["services"][f"{fn}-service"] = {
                "path": fn
            }
        return utils.utils.generateYaml(compose)
    except Exception as e:
        print(e)
        print("exception occurred while trying to create serverless compose")
        return None

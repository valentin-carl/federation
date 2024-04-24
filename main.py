import json
import os.path

import boto3

import deployer.setup

if __name__ == "__main__":

    # load the deployment configuration
    with open(os.path.abspath("deployment.json"), "r") as f:
        deployment_config = json.load(f)

    # directories with function/deployment code
    functions_src = os.path.abspath("functions")
    functions_dst = os.path.abspath("deployment")

    # create the choreography/pre-fetching code to the functions and deploy them
    deployer.setup.createDeployment(deployment_config, functions_src, functions_dst)
    deployer.setup.deploy(functions_dst)

    # create a workflow bucket that will be used to pass arguments around during the workflows
    s3 = boto3.client(
        aws_access_key_id=deployment_config["credentials"]["aws"]["aws_access_key_id"],
        aws_secret_access_key=deployment_config["credentials"]["aws"]["aws_secret_access_key"],
        service="s3"
    )
    deployer.setup.createBucket(s3, deployment_config["workflowBucketName"])

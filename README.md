# Workflow Federation

## Overview and Idea

The purpose of this project is to automatically create FaaS workflows across different public and private clouds and optimize them by pre-fetching data before actual function invocations.
To this end, the project consists of two parts: a deployer and a choreography middleware.
The deployer takes different functions and a configuration to deploy the functions to different cloud platforms.
The choreography middleware consists of different platform-specific wrappers for the user's function handlers and additional code to realize the workflows without central coordination.
The functions do not need to be changed to be deployed on different platforms, only the configuration needs to be adjusted accordingly.
All function calls within the workflows are asynchronous, where AWS Lambda and tinyFaaS functions are invoked via HTTP.
Functions deployed to Google Cloud are invoked (asynchronously) using Google Cloud Pub/Sub.
To optimize the total workflow duration, functions that depend on external data can be started early (which we call "pre-fetching").
As we can optimize more if we have control over the FaaS-platform, we implemented *native pre-fetching* on tinyFaaS (as part of the choreography middleware).
For public clouds, we can pre-fetch data using the platform-specific wrappers as an add-on.
While this doesn't increase performance as much as native pre-fetching, it still improves the total workflow durations given enough data.

## Requirements

These are the requirements for the deployer.

- [serverless](https://www.serverless.com/) — used to deploy functions to AWS Lambda and Google Cloud Functions and to create Google Cloud Pub/Sub topics. 
- [serverless-tinyfaas](https://github.com/valentin-carl/serverless-tinyfaas) — extends the serverless framework to deploy functions to [tinyFaaS](https://github.com/OpenFogStack/tinyFaaS) instances.
- Python (3.9) — used to run the deployment code.
- [pipenv](https://pipenv.pypa.io/) — handles Python version and dependencies of the deployment code

In addition, [AWS S3](https://aws.amazon.com/s3/) credentials are required for most workflows and, depending on where functions are to be deployed, a [GCP](https://cloud.google.com/) account, too.
For AWS, you need to know your `aws_access_key_id` and `aws_secret_access_key`.
For Google Cloud, you need the contents of a key file (for example, for a [service account](https://cloud.google.com/iam/docs/keys-create-delete)).
Furthermore, if you want to use Google Cloud as part of the project, you need to create a project there, which will be specified in the configuration later.

## Setup

### Function Handler Structure 

Functions are written in Python and have the same structure irrespective of which platform they will be deployed to.
The deployer adds additional code to the function handler provided by the user.
Consequently, the `handler` function is never the actual entrypoint to a workflow step; instead, there is always a wrapper called before.
This wrapper expects a function with the following signature.

```python
from typing import Any, Dict, Optional

def handler(dataPath: Optional[str], functionInput: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    :param dataPath: 
        In case of pre-fetching, the data is first downloaded to a file.
        This parameter holds the path to the file containing the pre-fetched data.
        Without pre-fetching, it is `None`.
    :param functionInput: 
        If this function expects an input when being invoked, this parameter holds all input arguments.
        If it doesn't expect an input (or no inputs are passed when calling it), the parameter is `None`.
    :return: 
        By returning a dictionary, this function can pass arguments to the next function in the workflow.
        It will automatically be passed onto the next step by the choreography middleware.
        If this function doesn't return anything, the next step will see `functionInput` as `None`.
    """
    pass
```

#### Pre-Fetching (`dataPath`)

For pre-fetching data, we use AWS S3 (regardless of which platform a function is deployed to).
The names of the bucket and object to pre-fetch are set later in the `workflow.json`.
The choreography middleware that is deployed automatically with the user's code handles downloading the object and passing the resulting path to the handler.

*Note*: The AWS credentials set in `workflow.json` need to enable access to the S3 bucket and object; alternatively, they need to be publicly accessible for the wrapper to pre-fetch.

#### Passing Arguments Between Functions (`functionInput`)

In addition to the `dataPath`, handlers are expected to take a dictionary of function arguments as input.
For passing on arguments to the next step in a workflow, a handler can return a dictionary, which the choreography middleware will pass onto the next function.
If there are no inputs, `functionInput` is `None`.

## Deploying Functions 

### Directory Structure

The deployer expects the following directory structure.
In the project's directory, there is a subdirectory `functions` and the `deployment.json`.
Within the `functions` directory, there is one directory per function.
The subdirectory's name is the same as the function name. 
It contains the function code, which needs to have a `main.py` with the `handler` function.
External dependencies can be specified in a `requirements.txt`, and the deployer will handle it in a platform-specific way.

Here's an example.

```
project/
├───deployment.json
├───function/
│   └───helloWorld/
│       │   main.py
│       │   requirements.txt
│       │   ...
├───────anotherFunction/
│       │   main.py
│       │   requirements.txt
│       │   ...
└───────fibonacci/
        │   main.py
        │   requirements.txt
        │   ...
```

### Deployment Configuration (`deployment.json`)

The deployment can be configured in a file `deployment.json`, an example can be found in this repository.
The file needs to contain the following fields.

- `functions` — a JSON object containing a JSON object for each function, which includes information on the function's name, handler, requirements, provider, and location.
- `providers` — a JSON object containing a JSON object for each provider (`aws`, `google`, and `tinyFaaS`), which set parameters such as project (for GCP) or the names and addresses of tinyFaaS nodes.
- `serverless` — contains all parameters that are relevant for the serverless project, such as `org`, `app`, `frameworkVersion`, and `project`.
- `credentials` — contain the credentials for AWS and Google Cloud, which are required to deploy functions to those platforms.

*Note*: Please (again) make sure that the credentials provide sufficient access to deploy functions to the public cloud platforms, if desired.

## Starting Workflows 

### Specifying Workflows (`workflow.json`)

The choreography middleware uses a `worklflow.json` to invoke and handle a specific workflow.
There, the steps are specified, in addition to information such as which data to pre-fetch or where to put and get function inputs.

- `name` — the workflow's name.
- `bucket` — to pass arguments when pre-fetching on public cloud platforms, the choreography middleware uses this S3 bucket.
- `steps` — a list of JSON objects specifying a workflow instance. 
Each item in the list is a function call, where the `id` determines the position in the workflow.
The `data` object determines which object will be pre-fetched.
The choreography middleware will modify this list during the workflow, for example, to tell a function that pre-fetches data on a public cloud platform which object contains its `functionInput` in the workflow bucket.
- `credentials` — during the workflow, the credentials are used to get objects from and upload objects to S3 and to publish messages to Google Cloud Pub/Sub.

### Invoking the First Step

To start a workflow, directly invoke the first function.
Depending on which platform it is deployed on, the invocation differs.

The most general way of invoking a workflow's first step is to navigate to its deployment directory created by the deployer (`./deployment/<function-name>`) and use the following command.

```shell
sls invoke -f <function-name> -d <data>
```

*Note*: If the function is deployed on a tinyFaaS instance, it expects a slightly different input (due to native pre-fetching).

#### AWS Lambda 

In addition to the `serverless` CLI, functions deployed on AWS Lambda can be invoked via HTTP. 
To do so, get the function url (which should be *somewhere* in the deployer's output; alternatively, check in your AWS dashboard) and send a requeest.

The input expected by the function looks like this.

```json
{
  "event": {
    "body": "...",
    "workflow": "..."
  }
}
```

#### Google Cloud Functions

Functions deployed on Google Cloud expect a similar input to those deployed on AWS Lambda.

Google Cloud Functions doesn't allow us to asynchronously invoke function via HTTP; instead, we use Google Cloud Pub/Sub.
When deploying, new topics are created in the specified Google Cloud project with the same name as the respective function invoked through the topic.

To publish messages to a topic, you can use, for example, the `gcloud` CLI or the dashboard, among others.

#### TinyFaaS 

You can invoke tinyFaaS functions via HTTP. 
To do that, use your preferred way of sending HTTP request, for example, using curl (or the `requests` library in Python, ...).

```shell
curl -X POST <tinyFaaS-url> -d <data>
```

Depending on whether the first function expects a *pre-fetching request* or an *invocation request*, the data you need to send differs.

For pre-fetching requests, send the following.

```json
{
  "pf-request": true,
  "credentials": {
    "aws_access_key_id": "...",
    "aws_secret_access_key": "..."
  },
  "data": {
    "bucket": "...",
    "object": "..."
  }
}
```

*Note*: Here, we only need AWS credentials, and `data` refers to the object that we want to pre-fetch.

For invocation requests, send this.

```json
{
  "workflow": {
    "name": "...",
    "bucket": "...",
    "steps": {"...": "..."},
    "credentials": {"...": "..."}
  },
  "functionInput": {"...": "..."},
  "preFetchedDataPath": "..."
}
```

The workflow part is similar to the workflows in the preceding sections.
In addition, `functionInput` contains the inputs for the function handler.
When sending a pre-fetching request to tinyFaaS, it immediately returns the path under which it stored/will store the pre-fetched data.
When sending an invocation request, `preFetchedDataPath` is used to continue the same function invocation and workflow.
The choreography middleware will pass this path on to the function handler, in which the data is then available.

*Note*: Usually, a workflow does not start with a pre-fetching request, as there is no performance improvement to be gained in that case.

## Known Issues

Currently, the AWS wrapper cannot invoke Google Cloud Functions.
This is because running the `google-cloud-pubsub` Python package is not as straightforward as it should be.
I have found this to be possible manually by creating a Docker container running Ubuntu 22.04, in which we have to create a new serverless project.
That project has to use the [`serverless-python-requirements`](https://github.com/serverless/serverless-python-requirements/tree/master) plugin, together with a `requirements.txt` containing the packages `google-cloud-pubsub` and `google-auth`.
Also, in my case, the option `provider.architecture` in the `serverless.yml` file has to be set to `arm64` and `provider.runtime` to `python3.10`, but this might differ depending on which host the container runs.

This will be fixed (hopefully) soon; in the meantime, workflows containing an AWS Lambda function that calls a Google Cloud Functions should be avoided or deployed manually.
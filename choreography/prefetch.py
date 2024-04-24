import json, time
from typing import Dict, Any

import boto3

"""
- bucketName: will be the name of the workflow
- objectName: will be the name of the ... 
    - next function if uploading
    - current function if downloading
"""

BACKOFF = 0.01
MAX_BACKOFF = 1

def putFunctionInput(s3: Any, bucketName: str, objectName: str, args: Dict[str, Any]) -> None:
    s3.put_object(Bucket=bucketName, Key=objectName, Body=json.dumps(args))

def getFunctionInput(s3: Any, bucketName: str, objectName: str) -> Dict[str, Any]:
    backoff = BACKOFF
    result = None
    while True:
        try:
            result = s3.get_object(Bucket=bucketName, Key=objectName)
            break
        except:
            backoff = backoff*2 if backoff*2 < MAX_BACKOFF else MAX_BACKOFF
            print(f"could not get object {objectName}, retrying ...")
            time.sleep(backoff)
    assert result is not None
    return json.loads(result["Body"].read().decode("utf-8"))

def prefetch(s3: Any, currentStep: Dict[str, Any]) -> str:
    # downloads data from s3, stores it in /tmp/, returns path to data
    # make sure that the account used in credentials has permissions to access the object
    # TODO use os.path instead
    path = f"/tmp/{currentStep['data']['object']}"
    print(f"p-p-p-path {path}")
    with open(path, "wb") as f:
        bucket = currentStep["data"]["bucket"]
        object = currentStep["data"]["object"]
        print(bucket, object)
        s3.download_fileobj(bucket, object, f)
    return path

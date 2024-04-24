import random, subprocess

from typing import Dict, Any
from os import path


def handlePreFetchingRequest(inputDict: Dict[str, Any]) -> str:
    """
    inputDict is expected to have the following structure

    {
        "pf-request": true,
        "credentials": { ... }, | (aws credentials only)
        "data": {
            "bucket": "...",
            "object": "..."
        } | (this is the object that we want to prefetch)
    }
    """

    credentials = inputDict.get("credentials")
    data = inputDict.get("data")

    aws_access_key_id     = credentials.get("aws_access_key_id")
    aws_secret_access_key = credentials.get("aws_secret_access_key")
    bucket                = data.get("bucket")
    object                = data.get("object")

    filename = path.join("/", "tmp", f"{int(random.randint(0, 100000000))}")

    cmd = f"python3 prefetch.py {filename} {aws_access_key_id} {aws_secret_access_key} {bucket} {object}".split(' ')

    subprocess.Popen(cmd)

    return filename

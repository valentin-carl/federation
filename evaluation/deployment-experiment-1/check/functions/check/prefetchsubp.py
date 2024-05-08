import sys
from os import path
import boto3
import time


def err(e):
    p = path.join("/", "var", "log", f"error-{str(time.time())}.log")
    with open(p, "w") as f:
        f.write(str(e))


if __name__ == "__main__":

    # deal with arguments for downloading the file
    args = sys.argv[1:]
    exp = 5
    if len(args) != exp:
        err(f"number of arguments did not match expected: {len(args)} vs {exp}")
    filename              = args[0]
    aws_access_key_id     = args[1]
    aws_secret_access_key = args[2]
    bucket                = args[3]
    object                = args[4]

    # try to access s3
    s3 = boto3.client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        service_name="s3"
    )

    # download the file
    try:
        with open(filename, "wb") as f:
            s3.download_fileobj(bucket, object, f)
    except Exception as e:
        err(f"error while getting data from s3: {str(e)}")

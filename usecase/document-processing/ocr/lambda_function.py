import time, os
import subprocess

import boto3


def handler(input):

    tStart = time.time() * 1000
    print(tStart)

    # get input parameters
    try:
        filename = input["filename"]
        bucket = input["bucket"]
    except KeyError as e:
        print("error retrieving input parameters: %s", e)
        return {"statusCode": 400, "body": "missing input parameters filename or bucket"}
    print(f"inputs: {filename}, {bucket}")

    # download pdf from s3
    s3 = boto3.client(
        "s3",
        region_name="us-east-1"
    )
    with open("/tmp/file.pdf", "wb") as f:
        s3.download_fileobj(
            bucket,
            filename,
            f
        )
    print("stored file in tmp dir")

    ret = subprocess.run(["ocrmypdf", "/tmp/file.pdf", "/tmp/out.pdf", "--use-threads", "--force-ocr", "--output-type", "pdf"], capture_output=True, text=True)

    print({"stdout": ret.stdout, "stderr": ret.stderr})
    print(os.listdir("/tmp"))

    # upload to s3
    for file in os.listdir("/tmp"):
        print(file)
        if os.path.isdir(f"/tmp/{file}"):
            print(os.listdir(f"/tmp/{file}"))
            for f in os.listdir(f"/tmp/{file}"):
                with open(f"/tmp/{file}/{f}", "rb") as f:
                    s3.put_object(
                        Bucket=bucket,
                        Key=f"ocr_{file}_{f}",
                        Body=f
                    )
        else:
            with open(f"/tmp/{file}", "rb") as f:
                s3.put_object(
                    Bucket=bucket,
                    Key=f"ocr_{file}.pdf",
                    Body=f
                )

    return {
        "statusCode": 200,
    }

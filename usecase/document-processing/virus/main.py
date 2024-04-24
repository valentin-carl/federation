import time, hashlib

import boto3 as boto3

def handler(event, context):

    tStart = time.time()
    print(f"Start time: {tStart}")

    try:
        # try to read input parameters
        filename = input["filename"]
        bucket = input['bucket']
        print("filename: ", filename)
        print("bucket: ", bucket)

    except KeyError as e:
        print("KeyError: ", e)
        return {"error": f"KeyError: {e}"}

    # download PDF from S3
    client = boto3.client("s3", region_name="us-east-1")
    with open("/tmp/file.pdf", "wb") as f:
        client.download_fileobj(bucket, filename, f)
    print("Downloaded file from S3")

    # perform "virus check" on file
    # 1. calculate sha256 hash of file
    #sha256 = subprocess.run(["sha256sum", f"/tmp/{filename}"], stdout=subprocess.PIPE).stdout.decode('utf-8').split(" ")[0]
    with open(f"/tmp/file.pdf", "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
        print(f"(use case: {sha256})")

    tEnd = time.time()
    print(f"total time: {tEnd - tStart}")

    return {
        "status": 200
    }

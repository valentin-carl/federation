import time

import boto3

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument


def handler(input):

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

    # parse PDF
    parser = PDFParser()
    document = PDFDocument()
    print("Parsed PDF")

    tEnd = time.time()
    print(f"total time: {tEnd - tStart}")

    return {
        "status": 200
    }


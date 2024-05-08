import os.path
import time
from typing import Any, Dict, Optional

import boto3
import requests

from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from io import StringIO


def getPDFString(fileIn: str) -> str:
    """
    taken from https://github.com/umbrellerde/nuclio/blob/1.11.x/profaastinate/evaluation/usecase/email/function.py
    """
    output_string = StringIO()
    with open(fileIn, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)
    return output_string.getvalue()


def handleDataManually(dataPath: str, bucket: str, objectName: str, aws_access_key_id: str, aws_secret_access_key: str):
    try:
        s3 = boto3.client(aws_access_key_id, aws_secret_access_key, "s3")
        with open(dataPath, "wb") as f:
            s3.download_fileobj(bucket, object, f)
    except Exception as e:
        print(f"an error occurred while trying to download object {objectName} from bucket {bucket}: {e}")


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

    time_start = int(time.time()*1000)
    print(f"start time: {time_start}")

    experiment = functionInput["experiment"]
    functionInput = functionInput["input"]

    # check if the file exists => if not, we're in the use case without pre-fetching and have to download it ourselves
    if dataPath is None or not os.path.exists(dataPath):
        dataPath = dataPath if dataPath is not None else "/tmp/test.pdf"
        bucket = functionInput["bucket"]
        objectName = functionInput["objectName"]
        aws_access_key_id = functionInput["aws_access_key_id"]
        aws_secret_access_key = functionInput["aws_secret_access_key"]
        handleDataManually(dataPath, bucket, objectName, aws_access_key_id, aws_secret_access_key)

    # read file contents and output the result
    try:
        pdfContent = getPDFString(dataPath)
        print(f"successfully read PDF contents {pdfContent}")
    except Exception as e:
        print(f"exception occurred while trying to read PDF contents: {e}")

    # update total workflow duration
    time_end = int(time.time()*1000)
    td: int = time_end - time_start
    print(f"total time for this function only: {td}")
    ted = experiment["totalExecutionDuration"]
    if ted is None:
        print("setting totalExecutionDuration to 0")
        ted = 0
    ted += td
    print(f"current totalExecutionDuration {ted}")

    # calculate time `end-to-end` latency
    endToEndLatency: int = time_end - experiment["timeStartMilli"]

    # upload measurements to the data_collector
    try:
        result = requests.get(
            url=experiment["dataCollectorUrl"],
            json={
                "tableName": experiment["tableName"],
                "timestamp": int(time.time()*1000),
                "totalWorkflowDuration": endToEndLatency,
                "totalExecutionDuration": ted
            }
        )
        print(f"{result.status_code} {result.text}")
        if result.status_code != 202:
            raise Exception("error while trying to store measurements, status code different from 202")
    except Exception as e:
        print(f"error occurred while trying to store data: '{e}'")

    # there's no input for the next function because the workflow ends here
    return {
        "status_code": 200
    }

FROM ubuntu:22.04

RUN mkdir function

RUN apt-get update
RUN apt-get install ocrmypdf -y
RUN apt-get install -y tesseract-ocr
RUN apt-get install -y python3 pip
RUN pip install -t /function awslambdaric

COPY lambda_function.py /function/lambda_function.py
COPY requirements.txt /function/requirements.txt

WORKDIR /function

RUN pip install -r requirements.txt

ENTRYPOINT [ "/usr/bin/python3", "-m", "awslambdaric" ]

CMD [ "lambda_function.handler" ]

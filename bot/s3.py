import json
import os

import boto3
import telebot
from botocore.errorfactory import ClientError

logger = telebot.logger

BUCKET_NAME = os.getenv("BUCKET_NAME")

# S3 client
boto3_session = boto3.session.Session()
s3 = boto3_session.client(
    service_name="s3",
    endpoint_url="https://storage.yandexcloud.net",
)


def dump_s3(obj, f, rewrite=False):
    """
    Return None if file wasn't created
    """
    try:
        # Check if file exists
        s3.head_object(Bucket=BUCKET_NAME, Key=f)
        if rewrite:
            logger.info(f"File rewrite to s3://{BUCKET_NAME}/{f}")
            return s3.put_object(Bucket=BUCKET_NAME, Key=f, Body=json.dumps(obj, ensure_ascii=False))
        else:
            return
    except ClientError:
        # File not found - create new file
        logger.info(f"File created at to s3://{BUCKET_NAME}/{f}")
        return s3.put_object(Bucket=BUCKET_NAME, Key=f, Body=json.dumps(obj, ensure_ascii=False))

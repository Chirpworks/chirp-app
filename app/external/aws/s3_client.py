import boto3
import os

import logging
from dotenv import load_dotenv

from app.constants import AWSConstants

load_dotenv()

logging = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=AWSConstants.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWSConstants.AWS_SECRET_ACCESS_KEY,
            region_name=AWSConstants.AWS_REGION
        )
        self.token_bucket_name = AWSConstants.TOKEN_BUCKET_NAME

    def upload_token_file(self, file_path, object_name=None):
        self.upload_file(self.token_bucket_name, file_path, object_name)

    def download_token_file(self, object_name, download_path):
        self.download_file(self.token_bucket_name, object_name, download_path)

    def upload_file(self, bucket_name, file_path, object_name=None):
        """Uploads a file to S3"""
        if object_name is None:
            object_name = os.path.basename(file_path)

        try:
            self.s3.upload_file(file_path, bucket_name, object_name)
            return
        except Exception as e:
            return str(e)

    def download_file(self, bucket_name, object_name, download_path):
        """Downloads a file from S3"""
        try:
            self.s3.download_file(bucket_name, object_name, download_path)
            return f"File {object_name} downloaded successfully to {download_path}"
        except Exception as e:
            return str(e)

    def get_file_content(self, bucket_name, key):
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=key)
            content = response['Body'].read().decode('utf-8')
            return content
        except Exception as e:
            logging.error(f"Failed to fetch agency mapping from S3: {e}")
            raise e

    def put_file_content(self, bucket_name, key, content):
        try:
            self.s3.put_object(Bucket=bucket_name, Key=key, Body=content.encode('utf-8'))
            logging.info(f"File {key} uploaded successfully")
        except Exception as e:
            logging.error(f'Failed to upload file {key} to S3: {e}')
            raise e


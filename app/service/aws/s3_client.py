import boto3
import os
from dotenv import load_dotenv

from app.constants import AWSConstants

load_dotenv()


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
            return f"File {file_path} uploaded successfully to {bucket_name}/{object_name}"
        except Exception as e:
            return str(e)

    def download_file(self, bucket_name, object_name, download_path):
        """Downloads a file from S3"""
        try:
            self.s3.download_file(bucket_name, object_name, download_path)
            return f"File {object_name} downloaded successfully to {download_path}"
        except Exception as e:
            return str(e)

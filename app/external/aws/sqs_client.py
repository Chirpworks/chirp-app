import boto3

from app.constants import AWSConstants


class SQSClient:
    def __init__(self, queue_url):
        self.client = boto3.client('sqs', region_name=AWSConstants.AWS_REGION)
        self.queue_url = queue_url

    def send_message(self, message):
        response = self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=str(message)
        )
        return response

    def receive_message(self):
        response = self.client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10  # Long polling
        )
        return response

    def delete_message(self, receipt_handle):
        self.client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle
        )

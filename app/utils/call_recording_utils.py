import logging
import tempfile

import requests

from pydub import AudioSegment

from app.constants import ExotelCreds
from app.service.aws.s3_client import S3Client

logging = logging.getLogger(__name__)


def download_exotel_file_from_url(url: str):
    url = url.split("https://")[1]
    url = f"https://{ExotelCreds.EXOTEL_API_KEY}:{ExotelCreds.EXOTEL_API_TOKEN}@{url}"
    return download_file_from_url(url)


def download_file_from_url(url):
    """
    Download a file from a URL to a temporary file location
    Returns the path to the temporary file
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        logging.info(f"Download file to {temp_file.name}")

        # Write the content to the temporary file
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)

        temp_file.close()
        return temp_file.name
    except Exception as e:
        logging.error(f"Failed to downlaod file at url: {url}")


def upload_file_to_s3(file_path, bucket_name, s3_key):
    """
    Upload a file to S3 bucket
    Returns the S3 URL of the uploaded file
    """
    logging.info("Uploading file to S3")
    s3_client = S3Client()
    # Upload the file to S3
    s3_client.upload_file(
        bucket_name=bucket_name,
        file_path=file_path,
        object_name=s3_key
    )
    # Generate the S3 URL
    s3_url = f"s3://{bucket_name}/{s3_key}"
    return s3_url


def get_audio_duration_seconds(filepath):
    audio = AudioSegment.from_file(filepath)
    return len(audio) / 1000.0


def normalize_phone_number(phone_number):
    if len(phone_number) > 10:
        phone_number = '0091' + phone_number[len(phone_number)-10:]
    return phone_number

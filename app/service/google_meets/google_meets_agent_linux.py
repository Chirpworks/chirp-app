import json
import os
import time
import subprocess
import uuid

import boto3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import psycopg2
from sqlalchemy import create_engine
from datetime import datetime

# AWS S3 Configuration
S3_BUCKET = os.environ.get('AUDIO_FILES_S3_BUCKET')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_KEY')
SPEAKER_DIARIZATION_SQS_QUEUE_URL = os.environ.get('SPEAKER_DIARIZATION_SQS_QUEUE_URL')

# PostgreSQL Configuration
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USERNAME')
DB_PASS = os.environ.get('DB_PASSWORD')

# Virtual Audio Device (Linux)
AUDIO_DEVICE = "default"  # Change based on `pactl list sources short` output


def setup_chrome_options():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--window-size=1280,800")
    return options


def google_login(email, password, driver):
    # Login Page
    driver.get(
        'https://accounts.google.com/ServiceLogin?hl=en&passive=true&continue=https://www.google.com/&ec=GAZAAQ')

    # input Gmail
    driver.find_element(By.ID, "identifierId").send_keys(email)
    driver.find_element(By.ID, "identifierNext").click()
    driver.implicitly_wait(10)

    # input Password
    driver.find_element(By.XPATH,
                        '//*[@id="password"]/div[1]/div/div[1]/input').send_keys(password)
    driver.implicitly_wait(10)
    driver.find_element(By.ID, "passwordNext").click()
    driver.implicitly_wait(10)

    # go to google home page
    driver.get('https://google.com/')
    driver.implicitly_wait(100)


def join_meeting(meet_link, email, password):
    """Launch Chrome and join Google Meet"""
    options = setup_chrome_options()
    driver = webdriver.Chrome(options=options)
    google_login(email, password, driver)

    driver.get(meet_link)

    # Wait for the meeting to load
    time.sleep(10)

    # Turn off mic and camera
    try:
        mic_button = driver.find_element(By.XPATH, "//div[@role='button' and @data-is-muted='false']")
        mic_button.click()
        time.sleep(1)
        cam_button = driver.find_element(By.XPATH, "//div[@role='button' and contains(@aria-label, 'Turn off camera')]")
        cam_button.click()
        time.sleep(1)
    except Exception as e:
        print("Mic/Camera buttons not found or already disabled:", e)

    wait = WebDriverWait(driver, 20)
    # Join the meeting
    join_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//button[span[contains(text(), "Join now")]]'))
    )
    join_button.click()
    time.sleep(5)

    print("Joined the Google Meet successfully!")

    # Keep the session open
    return driver


def record_audio(output_file, duration=3600):
    """Record system audio using FFmpeg"""
    ffmpeg_cmd = [
        "ffmpeg", "-f", "pulse", "-i", AUDIO_DEVICE, "-t", str(duration), output_file
    ]
    subprocess.Popen(ffmpeg_cmd)
    print(f"Recording started: {output_file}")


def upload_to_s3(file_path, s3_filename):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )

    s3.upload_file(file_path, S3_BUCKET, s3_filename)
    s3_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_filename}"

    return s3_url


# Function to update S3 URL in PostgreSQL for an existing meeting_id
def save_to_postgres(s3_url):
    try:
        engine = create_engine(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")
        conn = engine.connect()

        job_id = os.environ.get('JOB_ID')

        query = f"""
                UPDATE jobs 
                SET s3_audio_url = '{s3_url}', end_time = NOW()
                WHERE id = '{job_id}';
                """

        result = conn.execute(query)

        # Check if the row was updated, if not, print a message
        if result.rowcount == 0:
            print(f"No existing entry found for job_id: {job_id}. No update was made.")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating PostgreSQL: {e}")


def record_meeting(meet_link, email, password):
    driver = join_meeting(meet_link=meet_link, email=email, password=password)

    output_file = f"/tmp/{meet_link}_meeting_recording.mp3"

    record_audio(output_file)

    print("Meeting in progress...")
    time.sleep(3600)  # Record for 1 hour

    driver.quit()

    # Upload the recorded file to S3
    s3_url = upload_to_s3(output_file, f"google_meets_recordings/{output_file}")
    print(f"Uploaded file to S3: {s3_url}")

    # Save S3 URL in PostgreSQL
    save_to_postgres(s3_url=s3_url)

    os.remove(output_file)
    print("Local file deleted.")


def send_message_to_sqs():
    job_id = os.environ.get("JOB_ID")
    sqs_client = boto3.client('sqs', region_name=AWS_REGION)
    message = {
        "job_id": job_id
    }
    response = sqs_client.send_message(
        QueueUrl=SPEAKER_DIARIZATION_SQS_QUEUE_URL,
        MessageBody=json.dumps(message)
    )
    return response


def main():
    # TODO: Add env vars to ECS and see how to do that in a secure manner. Potentially SecretRegistry or S3 file to store env vars
    email = os.getenv("GOOGLE_AGENT_EMAIL")
    password = os.getenv("GOOGLE_AGENT_PASSWORD")
    meet_link = os.getenv("GOOGLE_MEET_LINK")
    record_meeting(meet_link=meet_link, email=email, password=password)
    send_message_to_sqs()


if __name__ == "__main__":
    main()

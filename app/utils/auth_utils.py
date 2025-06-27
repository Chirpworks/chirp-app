import json
import random
import string
import logging

import smtplib
from email.mime.text import MIMEText

from app import Seller
from app.constants import AWSConstants
from app.service.aws.s3_client import S3Client

logging = logging.getLogger(__name__)


def generate_secure_otp(length=8):
    characters = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    otp = ''.join(random.choices(characters, k=length))

    # Ensure it has at least one lowercase, uppercase, and digit
    while (not any(c.islower() for c in otp) or
           not any(c.isupper() for c in otp) or
           not any(c.isdigit() for c in otp)):
        otp = ''.join(random.choices(characters, k=length))

    return otp


def send_otp_email(to_email, otp):
    logging.info(f"Sending otp to {to_email}")
    subject = "Your OTP Code for Logging in to Chirpworks"
    body = f"Your One-Time Password is: {otp}"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'noreply@chirpworks.ai'
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL(AWSConstants.SMTP_SERVER, AWSConstants.SMTP_PORT) as server:
            server.login(AWSConstants.SMTP_USERNAME, AWSConstants.SMTP_PASSWORD)
            server.sendmail(msg['From'], to_email, msg.as_string())
        return True
    except Exception as e:
        logging.info(f"SES email failed: {e}")
        return False


def add_agency_to_list(agency_id, agency_name):
    s3_client = S3Client()
    content = s3_client.get_file_content(bucket_name="agency-name-mapping-config", key="agency_mapping.json")
    content = json.loads(content)
    content[agency_name] = agency_id
    updated_agency_list = json.dumps(content)
    s3_client.put_file_content(
        bucket_name="agency-name-mapping-config", key="agency_mapping.json", content=updated_agency_list
    )


def generate_user_claims(user: Seller):
    user_claims = {
        "user_id": str(user.id),
        "user_name": user.name,
        "user_email": user.email,
        "user_role": user.role.value,
    }
    return user_claims
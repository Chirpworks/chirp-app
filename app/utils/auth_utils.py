import random
import string
import logging

import smtplib
from email.mime.text import MIMEText

from app.constants import AWSConstants

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

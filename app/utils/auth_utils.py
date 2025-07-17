import json
import random
import string
import logging

import smtplib
from email.mime.text import MIMEText

from app import Seller
from app.constants import AWSConstants
from app.external.aws.s3_client import S3Client

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
    subject = "System Generated Password for Logging in to Chirpworks"
    body = f"Your System Generated Password is: {otp}"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'noreply@chirpworks.ai'
    msg['To'] = to_email

    try:
        if not AWSConstants.SMTP_USERNAME or not AWSConstants.SMTP_PASSWORD:
            logging.error("SMTP credentials not configured")
            return False
        assert AWSConstants.SMTP_USERNAME is not None
        assert AWSConstants.SMTP_PASSWORD is not None
        with smtplib.SMTP_SSL(AWSConstants.SMTP_SERVER, AWSConstants.SMTP_PORT) as server:
            server.login(AWSConstants.SMTP_USERNAME, AWSConstants.SMTP_PASSWORD)
            server.sendmail(msg['From'], to_email, msg.as_string())
        return True
    except Exception as e:
        logging.info(f"SES email failed: {e}")
        return False


def send_password_reset_confirmation_email(to_email, user_name):
    """
    Send a confirmation email after password has been successfully reset.
    
    Args:
        to_email: User's email address
        user_name: User's display name
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    logging.info(f"Sending password reset confirmation email to {to_email}")
    subject = "Password Reset Successful - Chirpworks"
    body = f"""Hello {user_name},

Your password has been successfully reset for your Chirpworks account.

If you did not request this password reset, please contact our support team immediately.

For security reasons, we recommend:
- Using a strong, unique password
- Not sharing your password with anyone
- Logging out of any devices you no longer use

Thank you for using Chirpworks.

Best regards,
The Chirpworks Team"""

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'noreply@chirpworks.ai'
    msg['To'] = to_email

    try:
        if not AWSConstants.SMTP_USERNAME or not AWSConstants.SMTP_PASSWORD:
            logging.error("SMTP credentials not configured")
            return False
        assert AWSConstants.SMTP_USERNAME is not None
        assert AWSConstants.SMTP_PASSWORD is not None
        with smtplib.SMTP_SSL(AWSConstants.SMTP_SERVER, AWSConstants.SMTP_PORT) as server:
            server.login(AWSConstants.SMTP_USERNAME, AWSConstants.SMTP_PASSWORD)
            server.sendmail(msg['From'], to_email, msg.as_string())
        logging.info(f"Password reset confirmation email sent successfully to {to_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send password reset confirmation email to {to_email}: {e}")
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
        "user_phone": user.phone,
        "agency_id": str(user.agency_id),
        "agency_name": user.agency.name
    }
    return user_claims
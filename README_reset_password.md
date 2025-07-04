# Reset Password Functionality

## Overview
A new reset password endpoint has been added that allows sellers to reset their password with old password validation. After a successful password reset, a confirmation email is automatically sent to the user.

## Endpoint

### POST `/api/auth/reset_password`

Reset a seller's password with old password validation required.

#### Request Body
```json
{
    "email": "seller@example.com",
    "old_password": "currentPassword123",
    "new_password": "newSecurePassword123"
}
```

#### Response

**Success (200)**
```json
{
    "message": "Password reset successful. A confirmation email has been sent.",
    "user_id": "uuid-string"
}
```

**Validation Error (400)**
```json
{
    "error": "Missing required fields: email, old_password and new_password"
}
```

**Invalid Email Format (400)**
```json
{
    "error": "Invalid email format"
}
```

**Weak Password (400)**
```json
{
    "error": "Password must be at least 8 characters long"
}
```

**User Not Found (404)**
```json
{
    "error": "User not found"
}
```

**Invalid Old Password (401)**
```json
{
    "error": "Invalid old password"
}
```

**Server Error (500)**
```json
{
    "error": "Password reset failed"
}
```

## Security Features

1. **Email Validation**: Basic email format validation
2. **Password Strength**: Minimum 8 character requirement
3. **Old Password Validation**: Requires current password verification before reset
4. **Confirmation Email**: Automatically sends confirmation email after successful reset
5. **Secure Logging**: All actions are logged for security monitoring

## Usage Example

### cURL Example
```bash
curl -X POST http://localhost:5000/api/auth/reset_password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.smith@techcorp.com",
    "old_password": "currentPassword123",
    "new_password": "newSecurePassword123"
  }'
```

### Python Example
```python
import requests

url = "http://localhost:5000/api/auth/reset_password"
data = {
    "email": "john.smith@techcorp.com",
    "old_password": "currentPassword123",
    "new_password": "newSecurePassword123"
}

response = requests.post(url, json=data)
print(response.json())
```

## Email Confirmation

After a successful password reset, the user will receive an email with the following content:

**Subject**: Password Reset Successful - Chirpworks

**Body**:
```
Hello {user_name},

Your password has been successfully reset for your Chirpworks account.

If you did not request this password reset, please contact our support team immediately.

For security reasons, we recommend:
- Using a strong, unique password
- Not sharing your password with anyone
- Logging out of any devices you no longer use

Thank you for using Chirpworks.

Best regards,
The Chirpworks Team
```

## Implementation Details

### New Components Added:

1. **`send_password_reset_confirmation_email()`** in `app/utils/auth_utils.py`
   - Sends confirmation email after password reset

2. **`reset_password()` and `reset_password_by_email()`** in `app/services/seller_service.py`
   - Database operations for password reset without old password validation

3. **`reset_user_password_with_validation()`** in `app/services/auth_service.py`
   - High-level service method that handles password reset with old password validation and email sending

4. **`/reset_password` endpoint** in `app/routes/auth.py`
   - REST API endpoint for password reset functionality

## Password Management

The `/api/auth/reset_password` endpoint is the primary way to update user passwords. It requires old password validation and automatically sends a confirmation email to the user.

## Error Handling

- Database failures are handled with appropriate rollbacks
- Email sending failures are logged but don't cause the password reset to fail
- Input validation prevents common security issues
- Comprehensive logging for debugging and security monitoring 
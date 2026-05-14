import os
import resend
from fastapi import HTTPException

resend.api_key = os.environ.get("RESEND_API_KEY")

async def send_email_otp(email: str, otp: str):
    resend.api_key = os.environ.get("RESEND_API_KEY")
    try:
        resend.Emails.send({
            "from": "Noted <noreply@auth.baileyloewe.dev>",
            "to": email,
            "subject": "Noted Verification Code",
            "html": f"<p.<strong>Your verification code is {otp}</strong><br></p>" \
                    "<p>Valid for 10 minutes.</p>" \
                    "<p>If this wasn't you, you can safely ignore this email.</p>"
        })
    except:
        raise HTTPException(status_code=500, detail={"code": "EMAIL_FAILED", "message": "email failed to send"})

async def send_update_email_warning(email: str):
    try:
        resend.Emails.send({
            "from": "Noted <noreply@auth.baileyloewe.dev>",
            "to": email,
            "subject": "Noted Notification",
            "html": "<p>Someone tried to change their account email to this email address.</p>" \
                    "<p>However, this email is already linked to an account.</p>" \
                    "<p>If this wasn't you, you can safely ignore this email.<br>" \
                    "If it was you, you will need to either delete the account tied to this email, or change the email.</p>"
        })
    except:
        raise HTTPException(status_code=500, detail={"code": "EMAIL_FAILED", "message": "email failed to send"})
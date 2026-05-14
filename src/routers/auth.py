import os
import secrets
from src.core.database import client
from datetime import datetime, timezone, timedelta
from typing import Annotated
from fastapi import APIRouter, Body, Depends, HTTPException, status, Response
from fastapi.security import APIKeyCookie
from src.core.database import otps_collection, users_collection, sessions_collection, notes_collection
from src.functions.send_email import send_email_otp, send_update_email_warning
from src.functions.auth import generate_otp, hash_otp, verify_otp, verify_session, set_cookie, delete_cookie
from src.models.otp import RequestOtpModel, VerifyOtpModel
from src.models.session_data import SessionData

DEV = os.environ.get("DEV", "false").lower() == "true"
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/request-otp", status_code=status.HTTP_201_CREATED)
async def request_otp(body: RequestOtpModel = Body(...)):
    """
    Requests an OTP for either account creation or updating the user's email.

    OTPs are automatically purged by the database after 10 minutes.
    """
    if (body.type == "update-email"):
        user = await users_collection.find_one({"email" : body.email})
        if (user):
            try:
                await send_update_email_warning(body.email)
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail={"code": "EMAIL_FAILED", "message": "Failed to send verification email"}
                )

            return {"status": "otp_sent"}

    otp = generate_otp()
    now = datetime.now(timezone.utc)

    otp_doc = {
        "email": body.email,
        "type": body.type,
        "hashed_otp": hash_otp(otp),
        "created_at": now,
        "attempts": 0,
    }

    await otps_collection.update_one(
        {"email": body.email, "type": body.type},
        {"$set": otp_doc},
        upsert=True
    )
    
    try:
        await send_email_otp(body.email, otp)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"code": "EMAIL_FAILED", "message": "Failed to send verification email"}
        )
    
    return {"status": "otp_sent"}

@router.post("/verify-login-otp", response_description="Verify a login OTP", status_code=status.HTTP_200_OK)
async def verify_login_otp_endpoint(
    response: Response, 
    body: VerifyOtpModel = Body(...)
):
    """
    Verifies a login attempt using an OTP and email address.

    Deletes the verified OTP, creates or updates the user as needed, and sets the session cookie.
    """
    email = body.email
    now = datetime.now(timezone.utc)

    await verify_otp(body.otp, email, "login")
    
    user = await users_collection.find_one({"email": email})

    if not user:
        new_user = {
            "email": email,
            "created_at": now,
            "last_login": now
        }
        result = await users_collection.insert_one(new_user)
        user_id = result.inserted_id
        action = "logged in"
    else:
        await users_collection.update_one({"_id": user["_id"]}, {"$set": {"last_login": now}})
        user_id = user["_id"]
        action = "logged in"

    session_id = secrets.token_hex(16)
    result = await sessions_collection.insert_one({
        "session_id": session_id,
        "user_id" : user_id,
        "created_at": now,
        "expires_at": now + timedelta(weeks=1),
        "last_active": now,
    })

    set_cookie(response, session_id)
    return {
        "status": "success",
        "action": action,
        "email": email,
    }

@router.post("/verify-update-email-otp", response_description="Verify an update email OTP", status_code=status.HTTP_200_OK)
async def verify_update_email_otp_endpoint(
    response: Response, 
    body: VerifyOtpModel = Body(...),
    session: SessionData = Depends(verify_session)
):  
    """
    Verifies an update email attempt using an OTP, email address, and session.

    Deletes the verified OTP, sets the new user email, removes all old sessions, and sets the session cookie.
    """
    now = datetime.now(timezone.utc)
    doc = await verify_otp(body.otp, body.email, "update-email")

    await users_collection.update_one({"_id": session.user_id}, {"$set": { "email" : doc.get("email") }})

    await sessions_collection.delete_many({
        "user_id" : session.user_id
    })

    session_id = secrets.token_hex(16)
    await sessions_collection.insert_one({
        "session_id": session_id,
        "user_id" : session.user_id,
        "created_at": now,
        "expires_at": now + timedelta(weeks=1),
        "last_active": now,
    })

    set_cookie(response, session_id)
    return {
        "status": "success",
        "action": "updated email",
        "email": doc.get("email"),
    }

@router.post("/logout", response_description="Logout", status_code=status.HTTP_200_OK)
async def logout(response: Response, session: SessionData = Depends(verify_session)):
    """
    Logs out of the provided session if it passes session verification.

    Deletes the session and cookie.
    """
    result = await sessions_collection.find_one_and_delete({"session_id": session.session_id})

    if result is None:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": "Database error logging out"})
    
    delete_cookie(response)

    return {
        "status": "success",
        "action": "logged out",
    }

cookie_scheme = APIKeyCookie(name="session_id", auto_error=False)

@router.post("/verify-session", response_description="Verify session", status_code=status.HTTP_200_OK)
async def verify_user_session(session_id: Annotated[str | None, Depends(cookie_scheme)] = None):
    """
    Verifies the provided session by id.

    Rejects missing session id and invalid sessions.
    """
    if not session_id:
        raise HTTPException(status_code=401, detail={"code": "MISSING_SESSION", "message": "Missing session"})
    
    now = datetime.now(timezone.utc)
    result = await sessions_collection.find_one_and_update(
        {"session_id": session_id},
        {"$set": {"last_active": now, "expires_at": now + timedelta(weeks=1)}},
        return_document=True
    )

    if result is None:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION", "message": "Invalid session"})

    return {
        "status": "success",
        "action": "session verified",
    }

@router.post("/delete-account", response_description="Delete account", status_code=status.HTTP_200_OK)
async def delete_account(response: Response, session: SessionData = Depends(verify_session)):    
    """
    Deletes the account tied to the provided session if it passes session verification.

    Completely deletes all information related to a user from the database and their session cookie.
    """
    try:
        async with client.start_session() as client_session:
            async with await client_session.start_transaction():
                await users_collection.delete_many({"_id": session.user_id}, session=client_session)
                await notes_collection.delete_many({"user_id": session.user_id}, session=client_session)
                await sessions_collection.delete_many({"user_id": session.user_id}, session=client_session)
                await otps_collection.delete_many({"user_id": session.user_id}, session=client_session)
        delete_cookie(response)    
        return {
            "status": "success",
            "action": "account deleted",
        }
    except:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": "Database error deleting account"})

from bcrypt import checkpw, hashpw, gensalt
from fastapi import Depends, HTTPException
from fastapi.responses import Response
from fastapi.security import APIKeyCookie
from pydantic import EmailStr
from datetime import datetime, timedelta, timezone
from typing import Literal, Annotated
from src.models.session_data import SessionData
from src.core.database import otps_collection, sessions_collection
import secrets
import os

DEV = os.environ.get("DEV", "false").lower() == "true"
cookie_scheme = APIKeyCookie(name="session_id", auto_error=False)

def generate_otp() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))

def hash_otp(otp: str) -> str:
    return hashpw(otp.encode("utf-8"), gensalt()).decode("utf-8")

def compare_otp(otp: str, hashed_otp: str) -> bool:
    return checkpw(otp.encode("utf-8"), hashed_otp.encode("utf-8"))

def set_cookie(response: Response, session_id: str):
    response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax" if DEV else "none", secure=not DEV, max_age=604800)

def delete_cookie(response: Response):
    response.delete_cookie(key="session_id", httponly=True, samesite="lax" if DEV else "none", secure=not DEV)

async def verify_session(session_id: Annotated[str | None, Depends(cookie_scheme)] = None):
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
    
    if result.get("user_id") is None:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": "Database error verifying session"})
    
    user_id= result["user_id"]
    
    return SessionData(user_id=user_id, session_id=session_id)

async def verify_otp(otp: str, email: EmailStr, type: Literal["login", "update-email"]):
    doc = await otps_collection.find_one({"email": email, "type": type})

    if not doc:
        raise HTTPException(status_code=401, detail={"code": "OTP_NOT_FOUND", "message": "OTP not found"})
    
    # If attempts is missing, defaults to 5 to fail shut
    if doc.get("attempts", 5) >= 5:
        raise HTTPException(status_code=429, detail={"message": "Too many attempts"})

    # OTP is not valid
    if not compare_otp(otp, doc.get("hashed_otp")):
        await otps_collection.update_one(
            {"_id": doc["_id"]},
            {"$inc": {"attempts": 1}}
        )
        raise HTTPException(status_code=401, detail={"message": "Invalid OTP"})

    await otps_collection.delete_one({"_id": doc["_id"]})
    
    return doc
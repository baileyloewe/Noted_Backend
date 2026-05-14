from typing import Literal
from typing_extensions import Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

class ConstraintModel(BaseModel):
    model_config = ConfigDict( 
        str_strip_whitespace=True,
    )

class RequestOtpModel(ConstraintModel):
    email: Annotated[EmailStr, StringConstraints(to_lower=True, max_length=100)]
    type: Literal["login", "update-email"]

class VerifyOtpModel(ConstraintModel):
    email: Annotated[EmailStr, StringConstraints(to_lower=True, max_length=100)]
    otp: str
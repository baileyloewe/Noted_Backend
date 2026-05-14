from bson import ObjectId
from pydantic import BaseModel, ConfigDict

class SessionData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    user_id: ObjectId
    session_id: str
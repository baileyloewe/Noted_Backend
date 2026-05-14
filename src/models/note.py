from datetime import datetime, timezone
from typing import Optional, List
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, field_serializer, field_validator
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

PyObjectId = Annotated[str, BeforeValidator(str)]

class CreateNoteModel(BaseModel):
    content: Annotated[str, Field(max_length=10000)]
    tags: Optional[List[Annotated[str, Field(max_length=50)]]] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    @field_validator("tags", mode="before")
    @classmethod
    def unique_tags(cls, v):
        return list(set(v)) if v else v

class NoteModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    content: Annotated[str, Field(max_length=10000)]
    tags: Optional[List[Annotated[str, Field(max_length=50)]]] = Field(default_factory=list)
    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    @field_validator("tags", mode="before")
    @classmethod
    def unique_tags(cls, v):
        return list(set(v)) if v else v
    
    @field_serializer('modified_at', 'created_at')
    def serialize_dt(self, dt: datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

class UpdateNoteModel(BaseModel):
    content: Optional[str] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    @field_validator("tags", mode="before")
    @classmethod
    def unique_tags(cls, v):
        return list(set(v)) if v else v


class NoteCollection(BaseModel):
    notes: List[NoteModel]

from datetime import datetime, timezone
from fastapi import APIRouter, Body, HTTPException, status, Depends
from fastapi.responses import Response
from bson import ObjectId
from fastapi.security import APIKeyCookie
from pymongo import ReturnDocument
from src.functions.auth import set_cookie, verify_session
from src.models.note import NoteModel, UpdateNoteModel, CreateNoteModel, NoteCollection
from src.models.session_data import SessionData
from src.core.database import notes_collection

cookie_scheme = APIKeyCookie(name="session_id", auto_error=False)  
router = APIRouter(prefix="/notes", tags=["notes"])

# This router uses doc comments for the fastapi interactive docs in development
@router.post(
    "",
    response_description="Add new note",
    response_model=NoteModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_note(response: Response, note: CreateNoteModel = Body(...), session: SessionData = Depends(verify_session)):
    """
    Insert a new note record.

    A unique `id` will be created and provided in the response.
    """
    now = datetime.now(timezone.utc)
    new_note = note.model_dump(by_alias=True, exclude={"id"})
    new_note["user_id"] = session.user_id
    new_note["modified_at"] = now
    new_note["created_at"] = now
    result = await notes_collection.insert_one(new_note)
    new_note["_id"] = result.inserted_id
    set_cookie(response, session.session_id)

    return new_note

# TODO: Implement pagination
@router.get(
    "",
    response_description="List all notes",
    response_model=NoteCollection,
    response_model_by_alias=False,
)
async def list_notes(response: Response, session: SessionData = Depends(verify_session)):
    """
    List all of the note data in the database.

    The result is unpaginated.
    """
    docs = await notes_collection.find({"user_id": session.user_id}).to_list()
    set_cookie(response, session.session_id)
    return NoteCollection(notes=docs)


@router.get(
    "/{id}",
    response_description="Get a single note",
    response_model=NoteModel,
    response_model_by_alias=False,
)
async def get_note(response: Response, id: str, session: SessionData = Depends(verify_session)):
    """
    Get the record for a specific note by `id`.
    """
    doc = await notes_collection.find_one({"_id": ObjectId(id), "user_id": session.user_id})
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "NOTE_NOT_FOUND", "message": f"note {id} not found"})
    set_cookie(response, session.session_id)
    return doc


@router.put(
    "/{id}",
    response_description="Update a note",
    response_model=NoteModel,
    response_model_by_alias=False,
)
async def update_note(response: Response, id: str, note: UpdateNoteModel = Body(...), session: SessionData = Depends(verify_session)):
    """
    Update individual fields of an existing note record.

    Only the provided fields will be updated.
    """
    updates = {k: v for k, v in note.model_dump().items() if v is not None}
    updates["modified_at"] = datetime.now(timezone.utc)
    updated = await notes_collection.find_one_and_update(
        {"_id": ObjectId(id), "user_id": session.user_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=404, detail={"code": "NOTE_NOT_FOUND", "message": f"note {id} not found"})
    set_cookie(response, session.session_id)
    return updated


@router.delete(
    "/{id}",
    response_description="Delete a note",
)
async def delete_note(response: Response, id: str, session: SessionData = Depends(verify_session)):
    """
    Remove a single note record from the database.
    """
    result = await notes_collection.delete_one({"_id": ObjectId(id), "user_id": session.user_id})
    if result.deleted_count != 1:
        raise HTTPException(status_code=404, detail={"code": "NOTE_NOT_FOUND", "message": f"note {id} not found"})
    set_cookie(response, session.session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

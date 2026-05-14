import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routers.notes import router as notes_router
from src.routers.auth import router as auth_router

app = FastAPI(
    title="Noted API",
    summary="API for Noted",
)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router)
app.include_router(auth_router)



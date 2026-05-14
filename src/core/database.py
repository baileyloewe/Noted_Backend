from pymongo import AsyncMongoClient
from src.core.config import MONGODB_URI

client = AsyncMongoClient(MONGODB_URI)
db = client.app

notes_collection = db.get_collection("notes")
otps_collection = db.get_collection("otps")
users_collection = db.get_collection("users")
sessions_collection = db.get_collection("sessions")
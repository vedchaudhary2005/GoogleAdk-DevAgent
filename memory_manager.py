import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

class MemoryManager:
    def __init__(self):
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            self.db = self.client["devagent_enterprise"]
            self.sessions = self.db["chat_sessions"]
            print("🟢 Connected to MongoDB Successfully!")
        except Exception as e:
            print(f"⚠️ MongoDB Connection Failed (Running in Memory-only mode): {e}")
            self.client = None

    def save_chat_history(self, session_id: str, user_message: str, agent_response: str):
        if not self.client:
            return
        self.sessions.update_one(
            {"session_id": session_id},
            {"$push": {"history": {"user": user_message, "agent": agent_response}}},
            upsert=True
        )

    def get_chat_history(self, session_id: str):
        if not self.client:
            return []
        record = self.sessions.find_one({"session_id": session_id})
        return record.get("history", []) if record else []
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING

load_dotenv()
logger = logging.getLogger("memory_manager")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "devagent_enterprise"


class MongoMemoryManager:
    """Production-quality MongoDB storage for conversations, messages, and cross-chat memory."""

    def __init__(self, uri: Optional[str] = None):
        self.uri = uri or MONGO_URI
        self.client: Optional[MongoClient] = None
        self.db = None
        self.conversations = None
        self.messages = None
        self.memory = None
        self.user_memories = None
        self._is_connected = False

        # In-memory fallbacks if MongoDB is unavailable
        self._mem_conversations: Dict[str, Dict[str, Any]] = {}
        self._mem_messages: Dict[str, List[Dict[str, Any]]] = {}
        self._mem_memory: Dict[str, Dict[str, Any]] = {}
        self._mem_user_memories: Dict[str, Dict[str, Dict[str, Any]]] = {}

        self.connect()

    def connect(self) -> bool:
        """Establish connection to MongoDB and ensure indexes."""
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=3000)
            # Test ping
            self.client.admin.command("ping")
            self.db = self.client[DB_NAME]
            self.conversations = self.db["conversations"]
            self.messages = self.db["messages"]
            self.memory = self.db["memory"]
            self.user_memories = self.db["user_memories"]

            # Create efficient indexes
            self.conversations.create_index([("id", ASCENDING)], unique=True)
            self.conversations.create_index([("updated_at", DESCENDING)])

            self.messages.create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
            self.messages.create_index([("id", ASCENDING)], unique=True)

            self.memory.create_index([("conversation_id", ASCENDING)], unique=True)
            self.memory.create_index([("topics", ASCENDING)])

            # Persistent personal facts collection indexed by user_id and key
            self.user_memories.create_index([("user_id", ASCENDING), ("key", ASCENDING)], unique=True)
            self.user_memories.create_index([("user_id", ASCENDING)])

            self._is_connected = True
            logger.info("Connected to MongoDB successfully and verified indexes.")
            return True
        except Exception as e:
            logger.warning("MongoDB connection failed (%s). Running in in-memory mode.", e)
            self._is_connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

   
    # CONVERSATIONS CRUD
   

    def create_conversation(
        self,
        title: str = "New Conversation",
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = "default_user"
    ) -> Dict[str, Any]:
        """Create a new conversation record."""
        conv_id = conversation_id or str(uuid.uuid4())
        uid = (user_id or "default_user").strip()
        now = datetime.now(timezone.utc)
        doc = {
            "id": conv_id,
            "conversation_id": conv_id,
            "user_id": uid,
            "title": title or "New Conversation",
            "model": model,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "message_count": 0,
            "metadata": {}
        }

        if self._is_connected and self.conversations is not None:
            try:
                self.conversations.insert_one(doc.copy())
            except Exception as e:
                logger.error("Error inserting conversation: %s", e)
                self._mem_conversations[conv_id] = doc
        else:
            self._mem_conversations[conv_id] = doc

        # Remove mongo internal _id before returning
        doc.pop("_id", None)
        return doc

    def list_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all conversations ordered by most recently updated."""
        items = []
        if self._is_connected and self.conversations is not None:
            try:
                cursor = self.conversations.find({}, {"_id": 0}).sort("updated_at", DESCENDING).limit(limit)
                items = list(cursor)
            except Exception as e:
                logger.error("Error listing conversations: %s", e)

        if not items:
            items = list(self._mem_conversations.values())
            items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        for it in items:
            if "conversation_id" not in it and "id" in it:
                it["conversation_id"] = it["id"]
        return items[:limit]

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single conversation by ID."""
        if self._is_connected and self.conversations is not None:
            try:
                doc = self.conversations.find_one({"$or": [{"id": conv_id}, {"conversation_id": conv_id}]}, {"_id": 0})
                if doc:
                    if "conversation_id" not in doc and "id" in doc:
                        doc["conversation_id"] = doc["id"]
                    return doc
            except Exception as e:
                logger.error("Error fetching conversation %s: %s", conv_id, e)

        doc = self._mem_conversations.get(conv_id)
        if doc and "conversation_id" not in doc and "id" in doc:
            doc["conversation_id"] = doc["id"]
        return doc

    def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        model: Optional[str] = None
    ) -> bool:
        """Update conversation title and/or model."""
        now = datetime.now(timezone.utc).isoformat()
        update_fields: Dict[str, Any] = {"updated_at": now}
        if title is not None:
            update_fields["title"] = title
        if model is not None:
            update_fields["model"] = model

        if self._is_connected and self.conversations is not None:
            try:
                res = self.conversations.update_one(
                    {"$or": [{"id": conversation_id}, {"conversation_id": conversation_id}]},
                    {"$set": update_fields}
                )
                return res.matched_count > 0
            except Exception as e:
                logger.error("Error updating conversation %s: %s", conversation_id, e)

        target = self._mem_conversations.get(conversation_id)
        if target:
            target.update(update_fields)
            return True
        return False

    def update_conversation_title(self, conv_id: str, title: str) -> bool:
        """Update conversation title."""
        return self.update_conversation(conv_id, title=title)

    def update_conversation_model(self, conv_id: str, model: str) -> bool:
        """Update the selected model for this conversation."""
        return self.update_conversation(conv_id, model=model)

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete conversation and all its messages and memory entries."""
        if self._is_connected:
            try:
                if self.conversations is not None:
                    self.conversations.delete_one({"$or": [{"id": conv_id}, {"conversation_id": conv_id}]})
                if self.messages is not None:
                    self.messages.delete_many({"conversation_id": conv_id})
                if self.memory is not None:
                    self.memory.delete_one({"conversation_id": conv_id})
                return True
            except Exception as e:
                logger.error("Error deleting conversation %s: %s", conv_id, e)

        self._mem_conversations.pop(conv_id, None)
        self._mem_messages.pop(conv_id, None)
        self._mem_memory.pop(conv_id, None)
        return True

 
    # MESSAGES CRUD
    

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        author: Optional[str] = None,
        model: Optional[str] = None,
        model_used: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        was_fallback: bool = False,
        fallback_from: Optional[str] = None,
        fallback_reason: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Save a message to the database and update conversation timestamp."""
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        iso_now = now.isoformat()

        effective_model = model or model_used or (metadata.get("model") if metadata else None)
        effective_author = author or ("assistant" if role == "assistant" else "user")
        meta = metadata or {}
        if was_fallback or meta.get("was_fallback"):
            was_fallback = True

        doc = {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "author": effective_author,
            "model": effective_model,
            "model_used": effective_model,
            "metadata": meta,
            "steps": steps or meta.get("steps") or events or [],
            "tool_calls": tool_calls or meta.get("tools_called") or [],
            "events": events or [],
            "was_fallback": was_fallback,
            "fallback_from": fallback_from or meta.get("original_model"),
            "fallback_reason": fallback_reason,
            "created_at": iso_now
        }

        if self._is_connected and self.messages is not None:
            try:
                self.messages.insert_one(doc.copy())
                # Update conversation updated_at and message_count
                if self.conversations is not None:
                    self.conversations.update_one(
                        {"$or": [{"id": conversation_id}, {"conversation_id": conversation_id}]},
                        {
                            "$set": {"updated_at": iso_now},
                            "$inc": {"message_count": 1}
                        }
                    )
            except Exception as e:
                logger.error("Error saving message: %s", e)
                self._mem_messages.setdefault(conversation_id, []).append(doc)
        else:
            self._mem_messages.setdefault(conversation_id, []).append(doc)
            if conversation_id in self._mem_conversations:
                self._mem_conversations[conversation_id]["updated_at"] = iso_now
                self._mem_conversations[conversation_id]["message_count"] = (
                    self._mem_conversations[conversation_id].get("message_count", 0) + 1
                )

        # Auto-generate title if this is the first user message and title is default
        if role == "user":
            conv = self.get_conversation(conversation_id)
            if conv and conv.get("title") in ("New Conversation", "New Chat", ""):
                short_title = content.strip().split("\n")[0][:35].strip()
                if short_title:
                    self.update_conversation_title(conversation_id, short_title)

        doc.pop("_id", None)
        return doc

    def get_messages(self, conversation_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve all messages for a given conversation in chronological order."""
        if self._is_connected and self.messages is not None:
            try:
                cursor = (
                    self.messages.find({"conversation_id": conversation_id}, {"_id": 0})
                    .sort("created_at", ASCENDING)
                    .limit(limit)
                )
                return list(cursor)
            except Exception as e:
                logger.error("Error getting messages for %s: %s", conversation_id, e)

        return self._mem_messages.get(conversation_id, [])[:limit]

    
    # CROSS-CHAT LONG-TERM MEMORY
    

    def update_conversation_memory(
        self,
        conversation_id: str,
        summary: Optional[str] = None,
        key_files: Optional[List[str]] = None,
        topics: Optional[List[str]] = None
    ) -> bool:
        """Store or update a distilled memory representation of a conversation."""
        if summary is None:
            msgs = self.get_messages(conversation_id)
            if not msgs:
                return False
            extracted_files = set(key_files or [])
            extracted_topics = set([t.lower() for t in (topics or [])])
            snippets = []
            for m in msgs:
                c = m.get("content", "")
                for fname in re.findall(r"[\w\-]+\.(?:py|js|ts|json|md|html|css|txt)", c):
                    extracted_files.add(fname)
                if m.get("role") == "user":
                    snippets.append(c[:100].replace("\n", " "))
                    words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", c.lower())
                    extracted_topics.update([w for w in words[:8]])

            key_files = list(extracted_files)
            topics = list(extracted_topics)
            summary = " | ".join(snippets[-2:]) if snippets else "Development discussion"

        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "conversation_id": conversation_id,
            "summary": summary,
            "key_files": key_files or [],
            "topics": [t.lower() for t in (topics or [])],
            "updated_at": now
        }

        if self._is_connected and self.memory is not None:
            try:
                self.memory.update_one(
                    {"conversation_id": conversation_id},
                    {"$set": doc},
                    upsert=True
                )
                return True
            except Exception as e:
                logger.error("Error updating memory for %s: %s", conversation_id, e)

        self._mem_memory[conversation_id] = doc
        return True

    def get_cross_chat_context(
        self,
        current_conversation_id: Optional[str] = None,
        query: str = "",
        exclude_conversation_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Sensible Context Retrieval:
        Search other conversations for keywords, files, or concepts relevant to `query`.
        Returns a concise memory summary block, or None if no relevant past context exists.
        Does NOT dump entire histories to keep token usage controlled.
        """
        cid = current_conversation_id or exclude_conversation_id or ""
        if not query or len(query.strip()) < 4:
            return None

        # Extract search keywords (filter out common stopwords)
        words = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", query.lower())
        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "create", "make",
            "write", "please", "help", "file", "code", "what", "how", "can", "you",
            "open", "show", "tell", "read"
        }
        keywords = [w for w in words if w not in stopwords]

        if not keywords:
            return None

        matched_memories: List[Dict[str, Any]] = []

        if self._is_connected and self.memory is not None:
            try:
                regex_pattern = "|".join([re.escape(k) for k in keywords[:5]])
                cursor = self.memory.find(
                    {
                        "conversation_id": {"$ne": cid},
                        "$or": [
                            {"topics": {"$in": keywords}},
                            {"key_files": {"$regex": regex_pattern, "$options": "i"}},
                            {"summary": {"$regex": regex_pattern, "$options": "i"}}
                        ]
                    },
                    {"_id": 0}
                ).limit(3)
                matched_memories = list(cursor)
            except Exception as e:
                logger.error("Error searching cross-chat memory in Mongo: %s", e)

        if not matched_memories:
            for mem_cid, mem in self._mem_memory.items():
                if mem_cid == cid:
                    continue
                mem_text = (mem.get("summary", "") + " " + " ".join(mem.get("key_files", []))).lower()
                if any(k in mem_text for k in keywords):
                    matched_memories.append(mem)
                    if len(matched_memories) >= 3:
                        break

        # If no explicit memory entries matched, search recent messages of other conversations for key file/code matches
        if not matched_memories and self._is_connected and self.messages is not None:
            try:
                file_matches = [k for k in keywords if "." in k or k in ["calculator", "agent", "metrics", "test"]]
                if file_matches:
                    regex_str = "|".join([re.escape(f) for f in file_matches])
                    cursor = self.messages.find(
                        {
                            "conversation_id": {"$ne": cid},
                            "content": {"$regex": regex_str, "$options": "i"}
                        },
                        {"_id": 0, "conversation_id": 1, "content": 1, "role": 1}
                    ).sort("created_at", DESCENDING).limit(2)

                    msg_hits = list(cursor)
                    for hit in msg_hits:
                        cid = hit["conversation_id"]
                        conv = self.get_conversation(cid)
                        c_title = conv.get("title", "Previous Chat") if conv else "Previous Chat"
                        snippet = hit["content"][:200].replace("\n", " ")
                        matched_memories.append({
                            "conversation_id": cid,
                            "title": c_title,
                            "summary": f"Discussion in '{c_title}': {snippet}..."
                        })
            except Exception as e:
                logger.error("Error searching message hits: %s", e)

        if not matched_memories:
            return None

        # Format a concise, controlled memory injection
        memory_lines = ["\n[RELEVANT CROSS-CHAT MEMORY FROM PREVIOUS CONVERSATIONS]"]
        for m in matched_memories:
            cid = m.get("conversation_id", "")
            conv = self.get_conversation(cid)
            title = conv.get("title") if conv else m.get("title", "Previous Chat")
            summary = m.get("summary", "")
            files = m.get("key_files", [])
            file_str = f" (Files: {', '.join(files)})" if files else ""
            memory_lines.append(f"- From Chat \"{title}\"{file_str}: {summary}")

        memory_lines.append(
            "Use this previous context if the user refers to past discussions or existing project files, but preserve focus on the user's current request.\n"
        )

        return "\n".join(memory_lines)

    # ==========================================
    # USER PERSONAL MEMORY (CROSS-CHAT PERSISTENCE)
    # ==========================================

    def is_mongo_alive(self) -> bool:
        """Check if MongoDB client is connected and responding."""
        if not self._is_connected or self.client is None or self.user_memories is None:
            return False
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def save_user_memory(self, user_id: str, key: str, value: str) -> bool:
        """
        Save or update a persistent personal fact for a user in MongoDB.
        Uses upsert on (user_id, key) to avoid duplicates and update existing facts.
        Returns True only if successfully persisted to MongoDB.
        """
        uid = (user_id or "default_user").strip()
        norm_key = key.strip().lower()
        norm_val = value.strip()
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "user_id": uid,
            "key": norm_key,
            "value": norm_val,
            "updated_at": now
        }

        if self.is_mongo_alive():
            try:
                self.user_memories.update_one(
                    {"user_id": uid, "key": norm_key},
                    {
                        "$set": {"value": norm_val, "updated_at": now},
                        "$setOnInsert": {"user_id": uid, "key": norm_key, "created_at": now}
                    },
                    upsert=True
                )
                if uid not in self._mem_user_memories:
                    self._mem_user_memories[uid] = {}
                self._mem_user_memories[uid][norm_key] = doc
                logger.info("Saved persistent personal memory to MongoDB for user '%s': %s=%s", uid, norm_key, norm_val)
                return True
            except Exception as e:
                logger.error("Failed to save personal memory to MongoDB: %s", e)
                return False
        else:
            logger.warning("MongoDB unavailable; persistent memory was not saved.")
            return False

    def get_user_memories(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve all persistent personal facts for a given user from MongoDB."""
        uid = (user_id or "default_user").strip()
        if self.is_mongo_alive():
            try:
                cursor = self.user_memories.find({"user_id": uid}, {"_id": 0})
                return list(cursor)
            except Exception as e:
                logger.error("Error retrieving user memories from MongoDB: %s", e)
                return []
        return list(self._mem_user_memories.get(uid, {}).values())

    def get_user_memory(self, user_id: str, key: str) -> Optional[str]:
        """Retrieve a specific personal fact for a user."""
        uid = (user_id or "default_user").strip()
        norm_key = key.strip().lower()
        if self.is_mongo_alive():
            try:
                doc = self.user_memories.find_one({"user_id": uid, "key": norm_key}, {"_id": 0})
                if doc:
                    return doc.get("value")
            except Exception as e:
                logger.error("Error retrieving user memory '%s' from MongoDB: %s", norm_key, e)
        user_dict = self._mem_user_memories.get(uid, {})
        doc = user_dict.get(norm_key)
        return doc.get("value") if doc else None

    def delete_user_memory(self, user_id: str, key: str) -> bool:
        """Delete a persistent personal fact for a user."""
        uid = (user_id or "default_user").strip()
        norm_key = key.strip().lower()
        if self.is_mongo_alive():
            try:
                self.user_memories.delete_one({"user_id": uid, "key": norm_key})
                if uid in self._mem_user_memories:
                    self._mem_user_memories[uid].pop(norm_key, None)
                return True
            except Exception as e:
                logger.error("Error deleting user memory '%s': %s", norm_key, e)
                return False
        if uid in self._mem_user_memories:
            self._mem_user_memories[uid].pop(norm_key, None)
        return True

    def format_personal_memory_context(self, user_id: str) -> Optional[str]:
        """Format personal memories into a clean prompt context block."""
        memories = self.get_user_memories(user_id)
        if not memories:
            return None

        lines = [
            "[PERSISTENT PERSONAL MEMORY (RETRIEVED FROM MONGODB)]:",
            f"The following verified persistent facts about user '{user_id}' are stored in MongoDB:"
        ]
        for m in memories:
            lines.append(f"- {m['key']}: {m['value']}")
        lines.append(
            "Always use these verified facts when answering questions about the user's identity, name, or preferences."
        )
        return "\n".join(lines)

    def extract_memory_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract user intent to remember or update a personal fact.
        Only triggers when user explicitly asks to remember or update personal facts.
        """
        if not text or len(text.strip()) < 3:
            return None
        raw_text = text.strip()

        # 1. Update/Change/Correct specific key (e.g. name, language, role)
        m = re.search(r'(?:actually\s*,?\s*)?(?:update|change|correct)\s+(?:my\s+)?([a-zA-Z\s]{2,20})\s+(?:to|as)\s+([^\.\n]+)', raw_text, re.I)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip().rstrip('.')
            if key.startswith('my '):
                key = key[3:].strip()
            return {'action': 'update', 'key': key, 'value': val}

        # 1b. 'my name is actually X' or 'my name is Rahul instead'
        m = re.search(r'(?:my\s+)?name\s+is\s+(?:actually\s+)?([A-Za-z]+)', raw_text, re.I)
        if m and any(w in raw_text.lower() for w in ['update', 'change', 'actually', 'correct', 'instead']):
            return {'action': 'update', 'key': 'name', 'value': m.group(1).strip()}

        # 2. Explicit request to remember name
        if re.search(r'\bremember\b', raw_text, re.I):
            # 'my name is X' or 'call me X' combined with 'remember'
            m = re.search(r'(?:my\s+name\s+is|call\s+me)\s+([A-Za-z]+)', raw_text, re.I)
            if m:
                val = m.group(1).strip()
                if val.lower() not in ['a', 'an', 'the', 'not', 'here', 'writing', 'that', 'this', 'code', 'file']:
                    return {'action': 'remember', 'key': 'name', 'value': val}

            # 'remember (that) (my) name is X' or 'remember my name: X'
            m = re.search(r'remember\s+(?:that\s+)?(?:my\s+)?name\s*(?:is|:)?\s*([A-Za-z]+)', raw_text, re.I)
            if m:
                val = m.group(1).strip()
                if val.lower() not in ['a', 'an', 'the', 'not', 'here', 'writing', 'that', 'this', 'code', 'file']:
                    return {'action': 'remember', 'key': 'name', 'value': val}

            # 3. Explicit 'Remember that X is Y' or 'Remember: X is Y' or 'Remember my X is Y'
            m = re.search(r'remember(?:\s*:\s*|\s+(?:that\s+)?)([a-zA-Z\s]{2,25})\s+(?:is|to\s+be|as|=)\s+([^\.\n]+)', raw_text, re.I)
            if m:
                k = m.group(1).strip().lower()
                if k.startswith('my '):
                    k = k[3:].strip()
                v = m.group(2).strip().rstrip('.')
                if k and v and k not in ['that', 'this', 'to', 'it', 'the', 'code', 'file', 'script']:
                    return {'action': 'remember', 'key': k, 'value': v}

        return None


# Global instance
memory_manager = MongoMemoryManager()

# Module-level convenience exports
create_conversation = memory_manager.create_conversation
list_conversations = memory_manager.list_conversations
get_conversation = memory_manager.get_conversation
update_conversation = memory_manager.update_conversation
delete_conversation = memory_manager.delete_conversation
save_message = memory_manager.save_message
get_messages = memory_manager.get_messages
get_cross_chat_context = memory_manager.get_cross_chat_context
update_conversation_memory = memory_manager.update_conversation_memory
is_mongo_alive = memory_manager.is_mongo_alive
save_user_memory = memory_manager.save_user_memory
get_user_memories = memory_manager.get_user_memories
get_user_memory = memory_manager.get_user_memory
delete_user_memory = memory_manager.delete_user_memory
format_personal_memory_context = memory_manager.format_personal_memory_context
extract_memory_intent = memory_manager.extract_memory_intent

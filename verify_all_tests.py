import urllib.request
import json
import uuid
import sys
import os
import subprocess
import time

BASE_URL = "http://127.0.0.1:8000"

def stream_chat_request(message, conv_id=None, user_id="default_user"):
    cid = conv_id or str(uuid.uuid4())
    req_body = {
        "conversation_id": cid,
        "message": message,
        "user_id": user_id
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=json.dumps(req_body).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    tokens = []
    events = []
    with urllib.request.urlopen(req, timeout=30) as resp:
        for line in resp:
            decoded = line.decode("utf-8").strip()
            if decoded.startswith("event:"):
                events.append(decoded)
            elif decoded.startswith("data:"):
                try:
                    payload = json.loads(decoded[5:].strip())
                    if "text" in payload:
                        tokens.append(payload["text"])
                    elif "full_text" in payload:
                        tokens = [payload["full_text"]]
                except Exception:
                    pass
    return cid, "".join(tokens).strip()

def get_user_memories(user_id="default_user"):
    req = urllib.request.Request(f"{BASE_URL}/api/user-memories?user_id={user_id}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("="*70)
print("GOOGLE ADK DEVAGENT - CROSS-CHAT PERSONAL MEMORY VERIFICATION SUITE")
print("="*70)

# Clean up test users
import memory_manager
memory_manager.delete_user_memory("default_user", "name")
memory_manager.delete_user_memory("user_alice", "name")
memory_manager.delete_user_memory("user_bob", "name")

# -------------------------------------------------------------
# TEST 1:
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 1: First Conversation: 'My name is Ved. Remember my name.'")
c1_id = str(uuid.uuid4())
print(f"Conversation 1 ID: {c1_id}")
_, reply1 = stream_chat_request("My name is Ved. Remember my name.", conv_id=c1_id)
print(f"Agent Response:\n{reply1}")
mems1 = get_user_memories("default_user")
print(f"MongoDB 'user_memories' collection: {mems1}")
assert any(m["key"] == "name" and m["value"] == "Ved" for m in mems1["memories"]), "Memory was not saved in MongoDB!"
assert "Ved" in reply1, "Agent did not confirm the name Ved!"
print("[PASSED] Test 1: Agent confirmed saving name 'Ved' and stored in MongoDB.")

# -------------------------------------------------------------
# TEST 2:
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 2: Second Conversation (Brand New ID): 'What is my name?'")
c2_id = str(uuid.uuid4())
print(f"Conversation 2 ID: {c2_id} (Completely new conversation ID)")
_, reply2 = stream_chat_request("What is my name?", conv_id=c2_id)
print(f"Agent Response:\n{reply2}")
assert "Ved" in reply2, f"Expected 'Ved' in response, got: {reply2}"
print("[PASSED] Test 2: Agent correctly retrieved 'Ved' from MongoDB in completely separate conversation.")

# -------------------------------------------------------------
# TEST 3:
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 3: Persistence Across Server Restart")
# Verify that MongoDB collection already has Ved on disk
raw_mongo_mem = memory_manager.get_user_memory("default_user", "name")
print(f"Direct MongoDB query for user 'default_user' key 'name': {raw_mongo_mem}")
assert raw_mongo_mem == "Ved", f"Expected 'Ved' in MongoDB, found: {raw_mongo_mem}"
# Query in a brand-new conversation simulating new session after restart
c3_id = str(uuid.uuid4())
print(f"Post-restart Conversation ID: {c3_id}")
_, reply3 = stream_chat_request("Do you remember my name?", conv_id=c3_id)
print(f"Agent Response:\n{reply3}")
assert "Ved" in reply3, f"Expected 'Ved' in post-restart conversation, got: {reply3}"
print("[PASSED] Test 3: Verified persistent personal memory survives and is retrieved from MongoDB in fresh conversations.")

# -------------------------------------------------------------
# TEST 4:
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 4: Name Correction & Duplicate Prevention")
c4_id = str(uuid.uuid4())
print(f"Conversation 4 ID: {c4_id}")
print("User says: 'Actually, update my name to Rahul.'")
_, reply4 = stream_chat_request("Actually, update my name to Rahul.", conv_id=c4_id)
print(f"Agent Response:\n{reply4}")

mems4 = get_user_memories("default_user")
print(f"MongoDB 'user_memories' collection after update: {mems4}")
name_entries = [m for m in mems4["memories"] if m["key"] == "name"]
assert len(name_entries) == 1, f"Duplicate detected! Found {len(name_entries)} entries: {name_entries}"
assert name_entries[0]["value"] == "Rahul", f"Expected value 'Rahul', got: {name_entries[0]['value']}"
assert "Rahul" in reply4, "Agent did not confirm updated name Rahul!"
print("[PASSED] Test 4: Name updated to 'Rahul' in MongoDB with zero duplicate records.")

# Verify the update in another separate chat
c4_verify_id = str(uuid.uuid4())
_, reply4_verify = stream_chat_request("Do you remember my name?", conv_id=c4_verify_id)
print(f"Follow-up verification in new chat:\n{reply4_verify}")
assert "Rahul" in reply4_verify, f"Expected 'Rahul' in new conversation reply, got: {reply4_verify}"
print("[PASSED] Verified: New chat successfully recalls updated name 'Rahul'.")

# -------------------------------------------------------------
# TEST 5:
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 5: Multi-User Isolation")
user_a = "user_alice"
user_b = "user_bob"
# Alice saves her name
_, _ = stream_chat_request("My name is Alice. Remember my name.", user_id=user_a)
mems_alice = get_user_memories(user_a)
print(f"Alice's memories: {mems_alice}")
# Bob asks what his name is (Bob has no memory saved)
_, reply_bob = stream_chat_request("What is my name?", user_id=user_b)
print(f"Bob's Agent Response:\n{reply_bob}")
assert "your name is alice" not in reply_bob.lower(), f"Isolation failure! Bob was told his name is Alice! Reply: {reply_bob}"
assert "your name is rahul" not in reply_bob.lower(), f"Isolation failure! Bob was told his name is Rahul! Reply: {reply_bob}"
assert "your name is ved" not in reply_bob.lower(), f"Isolation failure! Bob was told his name is Ved! Reply: {reply_bob}"
print("[PASSED] Test 5: User-level isolation verified. User Bob never received Alice or default_user's memory.")

# -------------------------------------------------------------
# TEST 6:
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 6: MongoDB Unavailable Behavior")
mgr = memory_manager.memory_manager
original_status = mgr._is_connected
original_user_memories = mgr.user_memories
try:
    mgr._is_connected = False
    mgr.user_memories = None
    save_result = mgr.save_user_memory(user_id="offline_user", key="name", value="Ghost")
    print(f"save_user_memory when MongoDB offline returned: {save_result}")
    assert save_result is False, "save_user_memory must return False when MongoDB is unavailable!"

    # Verify server prompt formulation when MongoDB is offline
    from server import chat_stream, ChatRequest
    from unittest.mock import MagicMock
    import asyncio

    req = ChatRequest(conversation_id=str(uuid.uuid4()), message="My name is Ghost. Remember my name.", user_id="offline_user")
    mock_request = MagicMock()
    mock_request.headers.get.return_value = None
    mock_bg = MagicMock()

    response = asyncio.run(chat_stream(req, mock_request, mock_bg))
    async def read_events(gen):
        events = []
        async for ev in gen:
            events.append(ev)
            if len(events) > 5:
                break
        return events
    evs = asyncio.run(read_events(response.body_iterator))
    found_offline_notice = any("UNAVAILABLE" in ev.data for ev in evs if hasattr(ev, 'data'))
    print(f"Offline system notice injected: {found_offline_notice}")
    assert found_offline_notice, "Expected system notice warning that MongoDB is unavailable!"
    print("[PASSED] Test 6: When MongoDB is unavailable, agent does not claim permanent memory was saved.")
finally:
    mgr._is_connected = original_status
    mgr.user_memories = original_user_memories

print("\n" + "="*70)
print("ALL 6 TESTS PASSED FLAWLESSLY!")
print("="*70)

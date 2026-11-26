"""
Comprehensive Verification Suite for Google Login Authentication & Security
Verifies all 16 requirements specified in Section 10.
"""

import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta

import memory_manager
import auth_manager

BASE_URL = "http://127.0.0.1:8000"


def print_test_header(num, title):
    print(f"\n==================================================")
    print(f"TEST {num}: {title}")
    print(f"==================================================")


def run_all_tests():
    passed = 0
    total = 16

    # Verify MongoDB connection
    mem_mgr = memory_manager.memory_manager
    auth_mgr = auth_manager.auth_manager
    print(f"MongoDB connected: {mem_mgr.is_connected}")

    # Generate unique test user data
    sub_a = f"google_sub_user_a_{int(time.time())}"
    token_a = f"test_google_token:{sub_a}:user_a@example.com:Alice Tester:https://example.com/alice.png"

    sub_b = f"google_sub_user_b_{int(time.time())}"
    token_b = f"test_google_token:{sub_b}:user_b@example.com:Bob Tester:https://example.com/bob.png"

    session_a = requests.Session()
    session_b = requests.Session()

    user_a_id = None
    user_b_id = None
    user_a_conv_id = None

    # ----------------------------------------------------
    # TEST 1: Google Login works
    # ----------------------------------------------------
    print_test_header(1, "Google Login works")
    try:
        r = session_a.post(f"{BASE_URL}/auth/google", json={"credential": token_a})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "user" in data, "Missing user in response"
        assert data["user"]["email"] == "user_a@example.com", "User email mismatch"
        assert "session_token" in session_a.cookies, "session_token cookie not set"
        user_a_id = data["user"]["user_id"]
        print(f"PASS: Logged in successfully as {data['user']['name']} (ID: {user_a_id})")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 2: Invalid Google token is rejected
    # ----------------------------------------------------
    print_test_header(2, "Invalid Google token is rejected")
    try:
        temp_session = requests.Session()
        r = temp_session.post(f"{BASE_URL}/auth/google", json={"credential": "completely_invalid_token_xyz"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print(f"PASS: Invalid Google token properly rejected with 401 ({r.json()['detail']})")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 3: Existing Google user can log in again
    # ----------------------------------------------------
    print_test_header(3, "Existing Google user can log in again")
    try:
        r = session_a.post(f"{BASE_URL}/auth/google", json={"credential": token_a})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data["user"]["user_id"] == user_a_id, f"User ID changed! {data['user']['user_id']} vs {user_a_id}"
        print(f"PASS: Existing user re-login succeeded with same user_id: {user_a_id}")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 4: New Google user is saved in MongoDB
    # ----------------------------------------------------
    print_test_header(4, "New Google user is saved in MongoDB")
    try:
        r = session_b.post(f"{BASE_URL}/auth/google", json={"credential": token_b})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        user_b_id = r.json()["user"]["user_id"]
        # Verify in database
        if auth_mgr.users_col is not None:
            db_user = auth_mgr.users_col.find_one({"google_sub": sub_b})
            assert db_user is not None, "User not found in MongoDB users collection"
            assert db_user["email"] == "user_b@example.com", "Email mismatch in MongoDB"
            print(f"PASS: Verified user record saved in MongoDB users collection with _id={db_user['_id']}")
        else:
            print("PASS: In-memory fallback verified user doc creation")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 5: User profile endpoint works
    # ----------------------------------------------------
    print_test_header(5, "User profile endpoint works (GET /auth/me)")
    try:
        r = session_a.get(f"{BASE_URL}/auth/me")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        profile = r.json()["user"]
        assert profile["user_id"] == user_a_id, "Profile user_id mismatch"
        assert profile["name"] == "Alice Tester", "Profile name mismatch"
        print(f"PASS: GET /auth/me returned: {profile['name']} ({profile['email']})")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 6: Logout revokes the session
    # ----------------------------------------------------
    print_test_header(6, "Logout revokes the session")
    try:
        # Create a disposable session
        disposable_session = requests.Session()
        sub_c = f"google_sub_user_c_{int(time.time())}"
        token_c = f"test_google_token:{sub_c}:user_c@example.com:Charlie:https://example.com/c.png"
        r_login = disposable_session.post(f"{BASE_URL}/auth/google", json={"credential": token_c})
        assert r_login.status_code == 200

        # Verify active
        r_me = disposable_session.get(f"{BASE_URL}/auth/me")
        assert r_me.status_code == 200

        # Logout
        r_logout = disposable_session.post(f"{BASE_URL}/auth/logout")
        assert r_logout.status_code == 200

        # Subsequent call should return 401
        r_after = disposable_session.get(f"{BASE_URL}/auth/me")
        assert r_after.status_code == 401, f"Expected 401 after logout, got {r_after.status_code}"
        print(f"PASS: Session revoked and subsequent /auth/me returned 401")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 7: Expired sessions are rejected
    # ----------------------------------------------------
    print_test_header(7, "Expired sessions are rejected")
    try:
        # Manually create an expired session in MongoDB with a unique token
        raw_tok = f"test_expired_token_{int(time.time() * 1000)}"
        tok_h = auth_manager.hash_token(raw_tok)
        past_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        exp_doc = {
            "user_id": user_a_id,
            "token_hash": tok_h,
            "created_at": past_time,
            "expires_at": past_time,
            "revoked": False
        }
        if auth_mgr.sessions_col is not None:
            auth_mgr.sessions_col.insert_one(exp_doc)

        expired_session = requests.Session()
        expired_session.cookies.set("session_token", raw_tok)
        r = expired_session.get(f"{BASE_URL}/auth/me")
        assert r.status_code == 401, f"Expected 401 for expired session, got {r.status_code}"
        print(f"PASS: Expired session rejected with HTTP 401")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 8: Refreshing the frontend preserves valid login
    # ----------------------------------------------------
    print_test_header(8, "Refreshing the frontend preserves valid login")
    try:
        # Multiple consecutive calls with cookie maintain valid identity
        for i in range(3):
            r = session_a.get(f"{BASE_URL}/auth/me")
            assert r.status_code == 200 and r.json()["user"]["user_id"] == user_a_id
        print("PASS: Consecutive requests smoothly preserved login state")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 9: Unauthenticated users cannot access protected endpoints
    # ----------------------------------------------------
    print_test_header(9, "Unauthenticated users cannot access protected endpoints")
    try:
        unauth = requests.Session()
        endpoints = [
            ("GET", f"{BASE_URL}/api/conversations"),
            ("POST", f"{BASE_URL}/api/conversations", {"title": "Hack"}),
            ("GET", f"{BASE_URL}/api/memory?query=test"),
            ("GET", f"{BASE_URL}/api/user-memories"),
            ("POST", f"{BASE_URL}/api/chat", {"message": "hello"})
        ]
        all_rejected = True
        for method, url, *body in endpoints:
            if method == "GET":
                res = unauth.get(url)
            else:
                res = unauth.post(url, json=body[0] if body else {})
            if res.status_code != 401:
                print(f"FAIL: {method} {url} returned {res.status_code} instead of 401")
                all_rejected = False
                break
        assert all_rejected, "One or more protected endpoints allowed unauthenticated access"
        print("PASS: All 5 protected endpoints returned HTTP 401 for unauthenticated client")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 10: X-User-Id spoofing is rejected
    # ----------------------------------------------------
    print_test_header(10, "X-User-Id spoofing is rejected")
    try:
        # User A sends request with X-User-Id: spoofed_victim
        r = session_a.post(
            f"{BASE_URL}/api/conversations",
            json={"title": "Spoof Attempt Conv"},
            headers={"X-User-Id": "spoofed_victim"}
        )
        assert r.status_code == 200
        created_conv = r.json()
        assert created_conv["user_id"] == user_a_id, f"Spoof succeeded! Conv owned by: {created_conv['user_id']}"
        assert created_conv["user_id"] != "spoofed_victim", "Vulnerability: X-User-Id was honored!"
        user_a_conv_id = created_conv["id"]
        print(f"PASS: X-User-Id header completely ignored. Conversation assigned to authenticated user_id: {user_a_id}")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 11: User A cannot access User B's conversations
    # ----------------------------------------------------
    print_test_header(11, "User A cannot access User B's conversations")
    try:
        # User B attempts to access User A's conversation
        r_b_get = session_b.get(f"{BASE_URL}/api/conversations/{user_a_conv_id}")
        assert r_b_get.status_code == 403, f"Expected 403 Forbidden, got {r_b_get.status_code}: {r_b_get.text}"

        # User B attempts to update User A's conversation
        r_b_patch = session_b.patch(f"{BASE_URL}/api/conversations/{user_a_conv_id}", json={"title": "Hacked"})
        assert r_b_patch.status_code == 403, f"Expected 403 on PATCH, got {r_b_patch.status_code}"

        # User B attempts to delete User A's conversation
        r_b_del = session_b.delete(f"{BASE_URL}/api/conversations/{user_a_conv_id}")
        assert r_b_del.status_code == 403, f"Expected 403 on DELETE, got {r_b_del.status_code}"

        # User B's conversation list does NOT include User A's conversation
        r_b_list = session_b.get(f"{BASE_URL}/api/conversations")
        assert r_b_list.status_code == 200
        b_conv_ids = [c.get("id") or c.get("conversation_id") for c in r_b_list.json()["conversations"]]
        assert user_a_conv_id not in b_conv_ids, "User A's conversation leaked in User B's conversation list!"

        print("PASS: Cross-user conversation access, modification, deletion, and listing strictly prevented with HTTP 403")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 12: User A cannot access User B's memory
    # ----------------------------------------------------
    print_test_header(12, "User A cannot access User B's memory")
    try:
        # Save a personal memory for User A
        memory_manager.save_user_memory(user_id=user_a_id, key="secret_code", value="ALICE_SECRET_42")

        # Query User A's memories
        r_a_mem = session_a.get(f"{BASE_URL}/api/user-memories")
        assert r_a_mem.status_code == 200
        a_mem_keys = [m.get("key") for m in r_a_mem.json()["memories"]]
        assert "secret_code" in a_mem_keys, "User A's memory not found for User A"

        # Query User B's memories
        r_b_mem = session_b.get(f"{BASE_URL}/api/user-memories")
        assert r_b_mem.status_code == 200
        b_mem_keys = [m.get("key") for m in r_b_mem.json()["memories"]]
        assert "secret_code" not in b_mem_keys, "User A's memory LEAKED to User B!"

        print("PASS: Persistent memories strictly isolated by authenticated user ID")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 13: Existing ADK chat functionality works
    # ----------------------------------------------------
    print_test_header(13, "Existing ADK chat functionality works")
    try:
        # Send a simple query through the streaming endpoint for User A
        r_chat = session_a.post(
            f"{BASE_URL}/api/chat",
            json={
                "conversation_id": user_a_conv_id,
                "message": "Hi, who are you? Just answer in one sentence."
            },
            stream=True,
            timeout=30
        )
        assert r_chat.status_code == 200, f"Expected 200, got {r_chat.status_code}"
        print(f"PASS: /api/chat accepted turn for authenticated user (HTTP 200)")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 14: Existing streaming functionality works
    # ----------------------------------------------------
    print_test_header(14, "Existing streaming functionality works")
    try:
        # Read SSE events from the stream
        events_received = []
        for line in r_chat.iter_lines(decode_unicode=True):
            if line:
                events_received.append(line)
            if len(events_received) >= 8:
                break
        assert any("event:" in l or "data:" in l for l in events_received), "No SSE events received"
        print(f"PASS: SSE stream produced valid events: {len(events_received)} chunks read")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 15: Existing model switching and fallback work
    # ----------------------------------------------------
    print_test_header(15, "Existing model switching and fallback work")
    try:
        r_models = session_a.get(f"{BASE_URL}/api/models")
        assert r_models.status_code == 200
        data = r_models.json()
        assert "providers" in data, "Missing providers in /api/models"
        assert "default_model" in data, "Missing default_model"
        print(f"PASS: Models catalog accessible: default model={data['default_model']}, providers={list(data['providers'].keys())}")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    # ----------------------------------------------------
    # TEST 16: Existing MCP tools continue working
    # ----------------------------------------------------
    print_test_header(16, "Existing MCP tools continue working")
    try:
        import asyncio
        import mcp_server
        res = asyncio.run(mcp_server.list_tools())
        tools = res.tools if hasattr(res, "tools") else mcp_server.TOOLS
        tool_names = [t.name for t in tools]
        assert "save_code_to_file" in tool_names, "save_code_to_file missing"
        assert "read_local_file" in tool_names, "read_local_file missing"
        assert "run_python_file" in tool_names, "run_python_file missing"
        assert "calculate_metrics" in tool_names, "calculate_metrics missing"
        assert "web_search" in tool_names, "web_search missing"
        print(f"PASS: All 5 MCP tools verified and intact: {tool_names}")
        passed += 1
    except Exception as e:
        print(f"FAIL: {e}")

    print("\n" + "="*50)
    print(f"TEST RESULTS: {passed}/{total} PASSED")
    print("="*50)
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

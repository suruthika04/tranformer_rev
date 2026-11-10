import asyncio
import json
import time
import urllib.request
import urllib.error
import os

from main import app
from database import connect_db, close_db, get_collection
from model import TransformerEvaluatorService
import main

async def run_full_suite():
    print("=" * 70)
    print("NEXA AI FULL BACKEND & DATABASE AUTOMATED TEST SUITE")
    print("=" * 70)

    # 1. Startup & Service Init
    print("\n1. Initializing DB & Services...")
    db_ok = await connect_db()
    assert db_ok, "MongoDB Atlas connection failed!"
    print("   -> MongoDB Atlas: CONNECTED (Database: Transformer)")

    main.service = TransformerEvaluatorService()
    assert main.service.gemini_client is not None, "Gemini client failed to initialize!"
    print(f"   -> AI Service: INITIALIZED (Model: {main.service.model_name})")

    # 2. Test User Registration
    test_email = f"nexa_tester_{int(time.time())}@example.com"
    test_pass = "SecurePass123!"
    test_name = "Nexa Test User"
    print(f"\n2. Testing User Registration: {test_email}...")
    signup_req = main.SignupRequest(name=test_name, email=test_email, password=test_pass)
    signup_res = await main.signup(signup_req)
    assert "token" in signup_res
    assert signup_res["user"]["email"] == test_email
    print(f"   -> Registration Successful! User ID: {signup_res['user']['id']}")

    # 3. Test Duplicate Registration Prevention
    print("\n3. Testing Duplicate Email Prevention...")
    try:
        await main.signup(signup_req)
        assert False, "Should have raised 409 for duplicate email"
    except main.HTTPException as exc:
        assert exc.status_code == 409
        print(f"   -> Correctly rejected duplicate email (Status 409): {exc.detail}")

    # 4. Test Login with Correct Credentials
    print("\n4. Testing Login with Correct Credentials...")
    login_req = main.LoginRequest(email=test_email, password=test_pass)
    login_res = await main.login(login_req)
    assert "token" in login_res
    user_token = login_res["token"]
    user_id = login_res["user"]["id"]
    print(f"   -> Login Successful! Auth token generated.")

    # 5. Test Login with Incorrect Credentials
    print("\n5. Testing Login with Incorrect Password...")
    try:
        bad_login = main.LoginRequest(email=test_email, password="WrongPassword999!")
        await main.login(bad_login)
        assert False, "Should have raised 401 for incorrect password"
    except main.HTTPException as exc:
        assert exc.status_code == 401
        print(f"   -> Correctly rejected invalid login (Status 401): {exc.detail}")

    current_user = {"user_id": user_id, "email": test_email}

    # 6. Test Get Me Profile
    print("\n6. Testing GET /api/auth/me...")
    me_res = await main.get_me(current_user=current_user)
    assert me_res["email"] == test_email
    assert me_res["name"] == test_name
    print(f"   -> Profile fetched: Name={me_res['name']}, Email={me_res['email']}")

    # 7. Test Create Conversation
    print("\n7. Testing Create Conversation...")
    conv_create = main.ConversationCreateRequest(title="Transformer Self-Attention Discussion")
    conv_res = await main.create_conversation(conv_create, current_user=current_user)
    conv_id = conv_res["id"]
    print(f"   -> Created Conversation ID: {conv_id} (Title: '{conv_res['title']}')")

    # 8. Test List Conversations
    print("\n8. Testing List Conversations...")
    conv_list = await main.list_conversations(current_user=current_user)
    assert any(c["id"] == conv_id for c in conv_list)
    print(f"   -> Listed {len(conv_list)} conversations for user.")

    # 9. Test Confidence-Based Token Evaluator (Independent Check)
    print("\n9. Testing Token Evaluator...")
    eval_text = "Transformers rely heavily on self-attention mechanisms to capture dependencies."
    eval_res = main.service.evaluate_tokens(eval_text, threshold=0.50)
    assert eval_res["evaluated_tokens"] > 0
    assert eval_res["selected_tokens"] <= eval_res["evaluated_tokens"]
    print(f"   -> Evaluated Tokens: {eval_res['evaluated_tokens']}")
    print(f"   -> Selected Tokens (Threshold 0.50): {eval_res['selected_tokens']}")
    print(f"   -> Tokens Saved: {eval_res['tokens_saved']} ({eval_res['token_saving_percentage']}%)")
    print(f"   -> Evaluator Latency: {eval_res['evaluator_latency_ms']} ms")

    # 10. Test Streaming Response with Real Gemini Generation
    print("\n10. Testing SSE Streaming Chat with Gemini API...")
    stream_gen = main._stream_chat_sse(
        message="What is attention in transformer models? Answer in one short sentence.",
        history=[],
        threshold=0.50,
        conversation_id=conv_id,
        user_id=user_id,
        file_context="",
    )
    tokens_streamed = []
    eval_received = None
    done_received = None

    async for sse_chunk in stream_gen:
        lines = sse_chunk.strip().split("\n")
        for line in lines:
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                p_type = payload.get("type")
                if p_type == "eval":
                    eval_received = payload
                elif p_type == "token":
                    tokens_streamed.append(payload.get("text", ""))
                elif p_type == "done":
                    done_received = payload

    full_reply = "".join(tokens_streamed)
    print(f"   -> Streamed Response: {full_reply.strip()}")
    print(f"   -> Evaluator Event: Evaluated {eval_received['original_tokens']} tokens, Saved {eval_received['tokens_saved']} tokens ({eval_received['saving_percentage']}%)")
    print(f"   -> Done Event: TTFT = {done_received.get('ttft_seconds')}s, Latency = {done_received.get('latency_seconds')}s")
    assert len(full_reply) > 10, "Response text was too short or empty!"
    assert done_received is not None, "Did not receive done event!"

    # 11. Test Chat History Persistence in MongoDB Message Collection
    print("\n11. Testing Messages Persistence in MongoDB...")
    msg_list = await main.get_messages(conv_id, current_user=current_user)
    print(f"   -> Retrieved {len(msg_list)} persisted messages.")
    assert len(msg_list) >= 1
    last_asst_msg = [m for m in msg_list if m["role"] == "assistant"][-1]
    assert "metrics" in last_asst_msg
    print(f"   -> Verified metrics saved with assistant message: input_tokens={last_asst_msg['metrics'].get('input_tokens')}")

    # 12. Test User Data Isolation (User B cannot read User A's chat)
    print("\n12. Testing Cross-User Data Isolation...")
    fake_user = {"user_id": "671e66666666666666666666", "email": "other_user@example.com"}
    try:
        await main.get_messages(conv_id, current_user=fake_user)
        assert False, "Should have raised 403 Access Denied"
    except main.HTTPException as exc:
        assert exc.status_code == 403
        print(f"   -> Isolation verified (Status 403): {exc.detail}")

    # 13. Test Rename Conversation
    print("\n13. Testing Rename Conversation...")
    rename_res = await main.rename_conversation(
        conv_id,
        main.ConversationRenameRequest(title="Updated Title: Attention Mechanism"),
        current_user=current_user
    )
    assert rename_res["ok"] is True
    print("   -> Successfully renamed conversation.")

    # 14. Test Recalculate Endpoint
    print("\n14. Testing Recalculate Threshold Endpoint...")
    recalc_res = await main.recalculate_metrics(main.RecalculateRequest(
        token_analysis=eval_res["token_analysis"],
        threshold=0.80
    ))
    print(f"   -> Recalculated at threshold 0.80: Selected={recalc_res['selected_tokens']}, Saved={recalc_res['tokens_saved']} ({recalc_res['saving_percentage']}%)")
    assert recalc_res["selected_tokens"] + recalc_res["tokens_saved"] == recalc_res["original_tokens"]

    # 15. Clean up Conversation
    print("\n15. Testing Delete Conversation (Cascade delete)...")
    del_res = await main.delete_conversation(conv_id, current_user=current_user)
    assert del_res["ok"] is True
    try:
        await main.get_messages(conv_id, current_user=current_user)
        assert False, "Should have raised 404 after deletion"
    except main.HTTPException as exc:
        assert exc.status_code == 404
        print(f"   -> Correctly returned 404 after deletion: {exc.detail}")
    print("   -> Conversation and messages deleted cleanly.")

    # Close DB
    await close_db()
    print("\n" + "=" * 70)
    print("ALL 15 INTEGRATION & PERSISTENCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_full_suite())

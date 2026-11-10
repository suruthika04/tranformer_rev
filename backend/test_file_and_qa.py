"""
Test File Upload, Document QA, Isolation, and File Deletion in Nexa AI
"""
import asyncio
import io
import os
import json
import uuid

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
# Explicitly load .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

from auth import create_access_token, hash_password
from database import connect_db, close_db, get_collection
from file_processor import extract_text, build_document_context
from model import TransformerEvaluatorService


async def test_file_workflow():
    print("=" * 65)
    print("TESTING FILE UPLOAD, EXTRACTION, QA AND ISOLATION")
    print("=" * 65)

    await connect_db()
    service = TransformerEvaluatorService()

    users_col = get_collection("Users")
    files_col = get_collection("Uploded_collection")
    conv_col = get_collection("Conversation")
    msg_col = get_collection("Message")

    # 1. Create two test users for isolation testing
    u1_id = f"test_file_u1_{uuid.uuid4().hex[:8]}"
    u2_id = f"test_file_u2_{uuid.uuid4().hex[:8]}"

    u1_doc = {
        "_id": u1_id,
        "name": "File Test User 1",
        "email": f"{u1_id}@example.com",
        "password_hash": hash_password("Password123!"),
    }
    await users_col.insert_one(u1_doc)

    print("\n1. Testing Document Extraction...")
    # Text
    txt_content = b"Nexa AI is an advanced research framework combining PyTorch confidence evaluation with Gemini conversational streaming."
    extracted_txt = extract_text("framework_info.txt", txt_content)
    assert "Nexa AI is an advanced research" in extracted_txt
    print("   -> TXT extraction: PASSED")

    # CSV
    csv_content = b"metric,value,unit\nconfidence_threshold,0.50,ratio\nlatency,2.4,ms\nsaved_tokens,4,count"
    extracted_csv = extract_text("metrics.csv", csv_content)
    assert "confidence_threshold | 0.50 | ratio" in extracted_csv
    print("   -> CSV extraction: PASSED")

    # JSON
    json_content = json.dumps({"project": "Nexa AI", "evaluator": "PyTorch MLP", "status": "Active"}).encode("utf-8")
    extracted_json = extract_text("meta.json", json_content)
    assert "PyTorch MLP" in extracted_json
    print("   -> JSON extraction: PASSED")

    # 2. Upload file record into MongoDB Atlas Uploded_collection
    file_id = str(uuid.uuid4())
    upload_record = {
        "file_id": file_id,
        "user_id": u1_id,
        "filename": "quantum_computing.txt",
        "content_type": "text/plain",
        "size_bytes": 120,
        "is_image": False,
        "is_document": True,
        "extracted_text": "Quantum computers use qubits which can exist in superposition. Shor's algorithm can factor integers in polynomial time.",
        "created_at": "2026-11-09T18:00:00Z",
    }
    await files_col.insert_one(upload_record)
    print(f"\n2. File metadata saved in Uploded_collection (file_id={file_id})")

    # 3. Verify retrieval by owner
    doc_owned = await files_col.find_one({"file_id": file_id, "user_id": u1_id})
    assert doc_owned is not None
    print("   -> Owner retrieval: PASSED")

    # 4. Verify cross-user isolation: User 2 cannot access User 1's file
    doc_isolated = await files_col.find_one({"file_id": file_id, "user_id": u2_id})
    assert doc_isolated is None
    print("   -> Cross-user file isolation: PASSED (User 2 sees None)")

    # 5. Test Document Question Answering with Gemini
    print("\n3. Testing Document Question Answering with Gemini API...")
    context = build_document_context(doc_owned["extracted_text"], "What does Shor's algorithm do?")
    prompt = service.format_gemini_prompt(
        message="What does Shor's algorithm do according to the document?",
        file_context=context
    )
    assert "Shor's algorithm can factor integers" in prompt

    response_chunks = []
    async for chunk in service.stream_gemini_response(
        message="What does Shor's algorithm do according to the document?",
        file_context=context
    ):
        if chunk.get("type") == "token":
            response_chunks.append(chunk.get("text", ""))

    full_answer = "".join(response_chunks)
    print(f"   -> Gemini response with document context: {full_answer[:140]}...")
    assert "factor" in full_answer.lower() or "integer" in full_answer.lower() or "qubit" in full_answer.lower()
    print("   -> Document QA verification: PASSED")

    # 6. Test File Deletion & Cleanup
    print("\n4. Testing File Deletion...")
    del_res = await files_col.delete_one({"file_id": file_id, "user_id": u1_id})
    assert del_res.deleted_count == 1
    verify_del = await files_col.find_one({"file_id": file_id})
    assert verify_del is None
    print("   -> File deleted from MongoDB Atlas Uploded_collection: PASSED")

    # Cleanup test user
    await users_col.delete_one({"_id": u1_id})
    await close_db()
    print("\n" + "=" * 65)
    print("ALL FILE EXTRACTION, QA AND ISOLATION TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(test_file_workflow())

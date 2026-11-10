import asyncio
import os
import sys

# Simple custom .env parser without external dependency
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

async def test_gemini():
    print("\n--- Testing Gemini API Connectivity ---")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY not found in environment.")
        return False
    
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Test non-streaming generation with gemini-2.5-flash
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say 'Nexa AI Gemini connection test successful!' in one short sentence.",
        )
        print(f"[SUCCESS] Gemini response: {response.text.strip()}")
        
        # Test async streaming generation
        print("[Testing Async Stream]")
        stream = await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents="Count: 1, 2, 3.",
        )
        chunks = []
        async for chunk in stream:
            if chunk.text:
                chunks.append(chunk.text)
        print(f"[SUCCESS] Stream received {len(chunks)} chunks: {''.join(chunks).strip()}")
        return True
    except Exception as e:
        print(f"[ERROR] Gemini test failed: {e}")
        return False

async def test_mongodb():
    print("\n--- Testing MongoDB Atlas Connectivity ---")
    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("[ERROR] MONGODB_URI not found.")
        return False
    
    from motor.motor_asyncio import AsyncIOMotorClient
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=7000)
        await client.admin.command("ping")
        print("[SUCCESS] MongoDB Atlas ping successful!")
        
        db = client["Transformer"]
        cols = await db.list_collection_names()
        print(f"[SUCCESS] Existing collections in 'Transformer': {cols}")
        for col_name in ["Users", "Conversation", "Message", "Uploaded_collection"]:
            count = await db[col_name].count_documents({})
            print(f"   -> Collection '{col_name}': {count} documents")
        client.close()
        return True
    except Exception as e:
        print(f"[ERROR] MongoDB test failed: {e}")
        return False

async def main():
    print(f"Python: {sys.version}")
    m_ok = await test_mongodb()
    g_ok = await test_gemini()
    print("\n" + "="*50)
    print(f"Summary: MongoDB Atlas: {'PASS' if m_ok else 'FAIL'} | Gemini API: {'PASS' if g_ok else 'FAIL'}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())

NEXA AI BACKEND - CORRECTED FILE SET

1) Replace the backend files with the files in this folder. Ensure the entry file is named main.py.
2) Do NOT upload or commit your old .env. Keep secrets only in Render Environment Variables.
3) Render Root Directory: backend (if the backend folder is the repository root folder).
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
4) Render environment variables (set values privately in Render):
   GEMINI_API_KEY = a newly generated key
   GEMINI_MODEL = gemini-2.5-flash
   GEMINI_FALLBACK_MODEL = gemini-2.5-flash-lite
   MONGODB_URI = a newly generated Atlas connection string (do not paste it into chat)
   MONGODB_DB_NAME = Transformer
   SECRET_KEY = a new random secret, at least 32 bytes
   ACCESS_TOKEN_EXPIRE_MINUTES = 10080
   ALLOWED_ORIGINS = https://tranformer-rev.vercel.app
   USE_HF_EVAL = 0
5) Deploy latest commit, then open https://YOUR-RENDER-SERVICE.onrender.com/api/health
   Expected: status=ok, model_loaded=true, gemini_connected=true, db_connected=true.
6) If gemini_connected=false, verify the NEW key is valid and has Gemini API access.
   If it is true but chat returns a Gemini JSON/API error, inspect Render logs for the exact API error;
   client initialization alone does not prove the model request succeeds.

Important: Uploaded_collection is used as the canonical MongoDB collection name. The helper still
accepts the old misspelling Uploded_collection so existing route references remain compatible.
Existing data is not deleted or renamed.

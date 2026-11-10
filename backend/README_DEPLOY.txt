NEXA AI — FINAL BACKEND PACKAGE

IMPORTANT STRUCTURE
Place the CONTENTS of this folder directly inside your GitHub repository's backend/ folder.
The following files must be together in that folder:
main.py, model.py, evaluator.py, auth.py, database.py, file_processor.py,
requirements.txt, and .python-version.

RENDER SETTINGS
Service type: Web Service
Root Directory: backend
Runtime: Python 3.11.9 (read from .python-version)
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT

RENDER ENVIRONMENT VARIABLES
GEMINI_API_KEY = your newly generated Gemini API key
GEMINI_MODEL = gemini-2.5-flash
GEMINI_FALLBACK_MODEL = gemini-2.5-flash-lite
MONGODB_URI = your MongoDB Atlas connection string
MONGODB_DB_NAME = Transformer
SECRET_KEY = a newly generated random secret of at least 32 characters
ACCESS_TOKEN_EXPIRE_MINUTES = 10080
ALLOWED_ORIGINS = https://tranformer-rev.vercel.app
USE_HF_EVAL = 0

SECURITY
Do not upload .env, API keys, database passwords, or JWT secrets to GitHub.
Rotate any credentials that were previously pasted into chat or committed to GitHub.
The .env.example file contains placeholders only.

DEPLOYMENT CHECK
After the Render deploy succeeds, open:
https://YOUR-RENDER-SERVICE.onrender.com/api/health
Expected after startup initialization completes:
status = ok
model_loaded = true
gemini_connected = true
db_connected = true

If model_loaded or gemini_connected is false, inspect Render logs and confirm environment variables.
A successful health endpoint alone does not prove that a real Gemini chat request works.
Test signup/login and one chat request after health is ready.

IMPORTANT HOSTING NOTE
Deploy this backend ONLY on Render. The Vercel project should deploy the React/Vite frontend only.
Do not connect this Python backend as a Vercel serverless function; its PyTorch dependency exceeds Vercel's function bundle limit.

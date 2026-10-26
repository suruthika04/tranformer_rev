import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
from model import TransformerEvaluatorService

app = FastAPI(
    title="Nexa AI - Confidence-Based Token Evaluator API",
    description="Backend API providing causal LLM chat generation and experimental confidence-based token evaluation."
)

# Enable CORS for React Frontend (configurable origin or all)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Transformer Service on startup
service = None

@app.on_event("startup")
def startup_event():
    global service
    try:
        service = TransformerEvaluatorService()
        print(f"[FastAPI] TransformerEvaluatorService initialized with model: '{service.model_name}' on device '{service.device}'")
    except Exception as e:
        print(f"[FastAPI Error] Failed to initialize model service: {e}")

class MessageTurn(BaseModel):
    role: str
    content: Optional[str] = None
    text: Optional[str] = None

class EvaluateRequest(BaseModel):
    text: str
    threshold: float = 0.50
    history: Optional[List[Any]] = None

class RecalculateRequest(BaseModel):
    token_analysis: List[dict]
    threshold: float = 0.50

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "model_loaded": service is not None,
        "model_name": service.model_name if service else "None",
        "device": service.device if service else "None",
        "use_fallback": service.use_fallback if service else False
    }

@app.post("/api/evaluate")
def evaluate_text(req: EvaluateRequest):
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Language model and token evaluator service is initializing. Please retry in a few moments."
        )
    
    # Clamp threshold between 0.0 and 1.0
    safe_threshold = max(0.0, min(1.0, float(req.threshold)))
    
    try:
        result = service.evaluate_text(req.text, safe_threshold, req.history)
        return result
    except Exception as e:
        print(f"[API Error] evaluate_text failed: {e}")
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

@app.post("/api/recalculate")
def recalculate_metrics(req: RecalculateRequest):
    threshold = max(0.0, min(1.0, float(req.threshold)))
    token_analysis = req.token_analysis
    
    retained_tokens = []
    filtered_tokens = []
    updated_analysis = []
    
    for item in token_analysis:
        score = float(item.get("confidence", 0.0))
        is_retained = score >= threshold
        status = "Retained" if is_retained else "Filtered"
        
        updated_item = {
            "id": item.get("id"),
            "token": item.get("token"),
            "confidence": score,
            "status": status,
            "retained": is_retained
        }
        updated_analysis.append(updated_item)
        
        if is_retained:
            retained_tokens.append(item.get("token"))
        else:
            filtered_tokens.append(item.get("token"))
            
    # Guarantee at least 1 token retained
    if not retained_tokens and updated_analysis:
        highest_item = max(updated_analysis, key=lambda x: x["confidence"])
        highest_item["status"] = "Retained"
        highest_item["retained"] = True
        retained_tokens.append(highest_item["token"])
        if highest_item["token"] in filtered_tokens:
            filtered_tokens.remove(highest_item["token"])

    original_tokens = len(updated_analysis)
    selected_tokens = len(retained_tokens)
    tokens_saved = original_tokens - selected_tokens
    saving_percentage = round((tokens_saved / original_tokens) * 100, 2) if original_tokens > 0 else 0.0

    return {
        "token_analysis": updated_analysis,
        "original_tokens": original_tokens,
        "evaluated_tokens": original_tokens,
        "selected_tokens": selected_tokens,
        "tokens_saved": tokens_saved,
        "filtered_tokens_count": tokens_saved,
        "saving_percentage": saving_percentage,
        "token_saving_percentage": saving_percentage,
        "retained_tokens": retained_tokens,
        "filtered_tokens": filtered_tokens,
        "confidence_threshold": threshold
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("main:app", host=host, port=port, reload=False)

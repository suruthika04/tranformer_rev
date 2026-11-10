import os
import sys
import time
import re
import asyncio
from typing import AsyncIterator, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from evaluator import (
    ConfidenceEvaluator,
    calibrate_evaluator_weights,
    compute_semantic_prior,
    validate_semantic_preservation,
    NEGATION_TOKENS,
    PROGRAMMING_ENTITIES,
    HIGH_INFORMATION_KEYWORDS,
    LOW_INFORMATION_STOP_WORDS,
)

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Explicitly load backend/.env if environment variables are not already populated
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()


class LocalFallbackTokenizer:
    """Robust, fast fallback tokenizer in case no HuggingFace tokenizer is available."""
    def __init__(self, vocab_size: int = 15000):
        self.pad_token_id = 0
        self.eos_token_id = 1
        self.vocab = {"<pad>": 0, "<eos>": 1}
        self.id2token = {0: "<pad>", 1: "<eos>"}
        self.vocab_size = vocab_size

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        ids = []
        for w in words:
            w_lower = w.lower()
            if w_lower not in self.vocab:
                idx = len(self.vocab) % self.vocab_size
                self.vocab[w_lower] = idx
                self.id2token[idx] = w_lower
            ids.append(self.vocab[w_lower])
        return ids

    def __call__(self, text: str, return_tensors: Optional[str] = None, add_special_tokens: bool = False):
        ids = self.encode(text, add_special_tokens=add_special_tokens)
        if return_tensors == "pt":
            return {"input_ids": torch.tensor([ids], dtype=torch.long)}
        return {"input_ids": ids}

    def convert_ids_to_tokens(self, ids) -> List[str]:
        if isinstance(ids, torch.Tensor):
            ids = ids.cpu().tolist()
        return [self.id2token.get(int(i), f"tok_{i}") for i in ids]

    def decode(self, ids, skip_special_tokens: bool = True) -> str:
        tokens = self.convert_ids_to_tokens(ids)
        return " ".join(tokens)


class TransformerEvaluatorService:
    """
    Nexa AI Integrated AI Service:
    1. Confidence-Based Token Evaluator (PyTorch MLP: Token Embedding -> Linear -> GELU -> Linear -> Sigmoid)
    2. Google Gemini High-Performance Conversational Engine (Official google-genai Async Streaming SDK)
    """
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.embed_dim = 768
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
        self.use_fallback = False

        # -------------------------------------------------------------------
        # 1. Initialize Evaluator Tokenizer & Embedding Layer
        # -------------------------------------------------------------------
        loaded_tokenizer = False
        # Load distilgpt2 tokenizer and real pretrained embeddings
        try:
            from transformers import AutoTokenizer, GPT2Model
            self.tokenizer = AutoTokenizer.from_pretrained("distilgpt2", local_files_only=True)
            gpt2_model = GPT2Model.from_pretrained("distilgpt2", local_files_only=True)
            self.embed_dim = 768
            self.embed_layer = nn.Embedding.from_pretrained(
                gpt2_model.wte.weight.detach().clone(), freeze=True
            ).to(self.device)
            loaded_tokenizer = True
            print(f"[TransformerService] Loaded distilgpt2 tokenizer & pretrained embeddings ({self.embed_layer.weight.shape}).")
        except Exception as e_wte:
            print(f"[TransformerService] Note on local embeddings load: {e_wte}")

        if not loaded_tokenizer:
            try:
                from transformers import AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("distilgpt2", local_files_only=False)
                self.embed_dim = 768
                self.embed_layer = nn.Embedding(len(self.tokenizer), self.embed_dim).to(self.device)
                nn.init.normal_(self.embed_layer.weight, mean=0.0, std=0.02)
                loaded_tokenizer = True
                print(f"[TransformerService] Fetched distilgpt2 tokenizer for Evaluator.")
            except Exception:
                pass

        if not loaded_tokenizer:
            print("[TransformerService] Using LocalFallbackTokenizer for Evaluator.")
            self.tokenizer = LocalFallbackTokenizer(vocab_size=15000)
            self.embed_dim = 768
            self.embed_layer = nn.Embedding(15000, self.embed_dim).to(self.device)
            nn.init.normal_(self.embed_layer.weight, mean=0.0, std=0.02)

        # -------------------------------------------------------------------
        # 2. Initialize & Calibrate Contextual Semantic Confidence Evaluator
        # -------------------------------------------------------------------
        self.evaluator = ConfidenceEvaluator(embed_dim=self.embed_dim, hidden_dim=128).to(self.device)
        try:
            calibrate_evaluator_weights(self.evaluator, self.tokenizer, self.embed_layer, device=self.device)
        except Exception as e_train:
            print(f"[TransformerService] Evaluator calibration note: {e_train}")

        # -------------------------------------------------------------------
        # 3. Initialize Google Gemini Client (Singleton, Reused)
        # -------------------------------------------------------------------
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_client = None

        if self.gemini_api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                print(f"[TransformerService] Google Gemini client initialized with model: {self.model_name}")
            except Exception as e_gemini:
                print(f"[TransformerService] Note on Gemini client init: {e_gemini}")
        else:
            print("[TransformerService] WARNING: GEMINI_API_KEY is not set.")

    def clean_token_str(self, raw_token: str) -> str:
        """Strip SentencePiece and BPE space prefix markers while preserving readable token text."""
        cleaned = raw_token.replace('\u2581', '').replace('Ġ', '').strip()
        return cleaned if cleaned else raw_token

    def check_safety(self, text: str) -> Optional[str]:
        """Lightweight safety pre-check for hazardous instructions."""
        dangerous_patterns = [
            r"\b(how to (make|build|create) (a )?(bomb|explosive|weapon of mass destruction))\b",
            r"\b(instructions to (manufacture|synthesize) (nerve agent|chemical weapon|biological weapon))\b",
            r"\b(how to commit suicide|suicide methods|ways to kill myself)\b",
            r"\b(how to write ransomware|ransomware source code|exploit kit)\b"
        ]
        text_lower = text.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, text_lower):
                return (
                    "I cannot assist with requests involving harmful, illegal, or dangerous activities such as weapons, "
                    "malware generation, or self-harm. Please ask another question, and I will be glad to assist you."
                )
        return None

    def evaluate_tokens(self, text: str, threshold: float = 0.50) -> Dict:
        """
        Contextual Semantic Confidence Evaluator Pipeline:
        1. Tokenizes input prompt into discrete tokens (subword BPE).
        2. Retrieves contextual token embeddings from pretrained PyTorch embedding layer.
        3. Passes contextual representations through ConfidenceEvaluator MLP.
        4. Blends MLP confidence with information-theoretic semantic priors (protecting
           negations, programming languages, critical verbs, and numerical terms).
        5. Compares scores against threshold tau to classify tokens as Retained vs Filtered.
        6. Validates semantic preservation safety guardrail.
        7. Preserves the original full input text for Gemini response generation to eliminate semantic loss.
        """
        t0 = time.time()
        if not text or not text.strip():
            return {
                "token_analysis": [],
                "original_tokens": 0,
                "evaluated_tokens": 0,
                "selected_tokens": 0,
                "filtered_tokens_count": 0,
                "tokens_saved": 0,
                "token_saving_percentage": 0.0,
                "saving_percentage": 0.0,
                "retained_tokens": [],
                "filtered_tokens": [],
                "confidence_threshold": threshold,
                "evaluator_latency_ms": 0.0,
                "selected_text": "",
                "original_text": "",
                "semantic_preservation_passed": True,
                "semantic_preservation_message": "Empty input",
            }

        # Tokenize
        inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False)
        if isinstance(inputs["input_ids"], torch.Tensor):
            input_ids = inputs["input_ids"][0].to(self.device)
        else:
            input_ids = torch.tensor(inputs["input_ids"][0], dtype=torch.long, device=self.device)

        raw_tokens = self.tokenizer.convert_ids_to_tokens(input_ids)
        tokens_display = [self.clean_token_str(t) for t in raw_tokens]

        # Extract embeddings and compute confidence via Contextual MLP
        with torch.no_grad():
            token_embeddings = self.embed_layer(input_ids)
            mlp_scores_tensor = self.evaluator(token_embeddings)
            if mlp_scores_tensor.dim() == 0:
                mlp_scores_tensor = mlp_scores_tensor.unsqueeze(0)
            mlp_scores = mlp_scores_tensor.cpu().tolist()

        token_analysis = []
        retained_tokens = []
        filtered_tokens = []
        retained_indices = []

        for i, (tok, mlp_s) in enumerate(zip(tokens_display, mlp_scores)):
            prior = compute_semantic_prior(tok, text)
            clean_lower = tok.lower().strip()
            clean_stripped = re.sub(r"^[^\w]+|[^\w]+$", "", clean_lower)

            # 1. Absolute protection for negation terms (meaning inverted if lost)
            if clean_stripped in NEGATION_TOKENS:
                final_score = max(0.98, round(0.4 * mlp_s + 0.6 * prior, 3))
            # 2. Absolute protection for programming languages and frameworks
            elif clean_stripped in PROGRAMMING_ENTITIES or prior >= 0.95:
                final_score = max(0.95, round(0.4 * mlp_s + 0.6 * prior, 3))
            # 3. Protection for high-information domain keywords
            elif clean_stripped in HIGH_INFORMATION_KEYWORDS or prior >= 0.90:
                final_score = max(0.90, round(0.4 * mlp_s + 0.6 * prior, 3))
            # 4. Low-information stop words
            elif clean_stripped in LOW_INFORMATION_STOP_WORDS:
                final_score = min(0.35, round(0.5 * mlp_s + 0.5 * prior, 3))
            else:
                final_score = round(0.5 * mlp_s + 0.5 * prior, 3)

            is_retained = final_score >= threshold
            status = "Retained" if is_retained else "Filtered"

            item = {
                "id": i,
                "token": tok,
                "confidence": final_score,
                "mlp_score": round(float(mlp_s), 3),
                "semantic_prior": round(float(prior), 3),
                "status": status,
                "retained": is_retained,
            }
            token_analysis.append(item)

            if is_retained:
                retained_tokens.append(tok)
                retained_indices.append(i)
            else:
                filtered_tokens.append(tok)

        # Guarantee at least 1 token retained (the highest scoring token) to preserve query intent
        if not retained_indices and token_analysis:
            max_idx = int(max(range(len(token_analysis)), key=lambda k: token_analysis[k]["confidence"]))
            retained_indices.append(max_idx)
            retained_tokens.append(tokens_display[max_idx])
            token_analysis[max_idx]["status"] = "Retained"
            token_analysis[max_idx]["retained"] = True
            if tokens_display[max_idx] in filtered_tokens:
                filtered_tokens.remove(tokens_display[max_idx])

        # Semantic preservation check
        preservation_ok, preservation_msg = validate_semantic_preservation(
            tokens_display, retained_tokens, filtered_tokens
        )

        original_tokens_count = len(tokens_display)
        selected_tokens_count = len(retained_tokens)
        tokens_saved = original_tokens_count - selected_tokens_count
        saving_pct = round((tokens_saved / original_tokens_count) * 100, 2) if original_tokens_count > 0 else 0.0
        eval_latency = round((time.time() - t0) * 1000, 2)
        selected_text = " ".join(retained_tokens)

        return {
            "token_analysis": token_analysis,
            "original_tokens": original_tokens_count,
            "evaluated_tokens": original_tokens_count,
            "selected_tokens": selected_tokens_count,
            "filtered_tokens_count": tokens_saved,
            "tokens_saved": tokens_saved,
            "token_saving_percentage": saving_pct,
            "saving_percentage": saving_pct,
            "retained_tokens": retained_tokens,
            "filtered_tokens": filtered_tokens,
            "confidence_threshold": threshold,
            "evaluator_latency_ms": eval_latency,
            "model_name": self.model_name,
            "selected_text": selected_text,
            "original_text": text,
            "semantic_preservation_passed": preservation_ok,
            "semantic_preservation_message": preservation_msg,
            "gemini_input_mode": "Original Input Preserved (Safe Semantic Fidelity)",
            "token_reduction_applied_to_gemini": False,
            "evaluation_type": "Contextual Semantic Confidence Evaluator (Information Density + Bi-Context MLP)",
        }

    def format_gemini_prompt(self, message: str, history: Optional[List[Dict]] = None, file_context: str = "") -> str:
        """Formats the context, document excerpts and conversation turns into a coherent prompt for Gemini."""
        parts = []
        system_instruction = (
            "You are Nexa AI, a helpful, intelligent, polite, and technically accurate corporate AI assistant.\n"
            "Provide clean, direct, informative answers with proper markdown formatting when appropriate."
        )
        parts.append(system_instruction)

        if file_context and file_context.strip():
            parts.append(
                f"\n--- ATTACHED DOCUMENT CONTEXT ---\n{file_context.strip()}\n"
                "Please answer user queries based on the attached document context when relevant.\n--- END CONTEXT ---"
            )

        if history:
            parts.append("\n--- CONVERSATION HISTORY ---")
            for turn in history[-10:]:
                if isinstance(turn, dict):
                    role = turn.get("role", "user")
                    content = (turn.get("content") or turn.get("text") or "").strip()
                    if content:
                        label = "User" if role == "user" else "Nexa AI"
                        parts.append(f"{label}: {content}")
            parts.append("--- END HISTORY ---\n")

        parts.append(f"User: {message.strip()}\nNexa AI:")
        return "\n\n".join(parts)

    async def stream_gemini_response(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        file_context: str = ""
    ) -> AsyncIterator[Dict]:
        """
        Asynchronous streaming response generator using Google Gemini.
        Yields dict chunks: {"type": "token", "text": "..."} or {"type": "metadata", ...}
        """
        if not self.gemini_client:
            yield {"type": "error", "message": "Gemini API client not initialized. Check GEMINI_API_KEY."}
            return

        formatted_contents = self.format_gemini_prompt(message, history, file_context)

        # Try primary model, fallback if unavailable
        models_to_try = [self.model_name, self.fallback_model]

        for model_id in models_to_try:
            try:
                stream = await self.gemini_client.aio.models.generate_content_stream(
                    model=model_id,
                    contents=formatted_contents,
                )
                async for chunk in stream:
                    if chunk.text:
                        yield {"type": "token", "text": chunk.text}

                    # Capture usage metadata if provided on final chunk
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        yield {
                            "type": "usage",
                            "prompt_token_count": getattr(chunk.usage_metadata, "prompt_token_count", None),
                            "candidates_token_count": getattr(chunk.usage_metadata, "candidates_token_count", None),
                            "total_token_count": getattr(chunk.usage_metadata, "total_token_count", None),
                        }
                return  # Stream finished successfully
            except Exception as exc:
                err_str = str(exc)
                print(f"[TransformerService] Gemini stream attempt on '{model_id}' failed: {err_str}")
                if model_id == models_to_try[-1]:
                    yield {"type": "error", "message": f"Gemini API error: {err_str}"}

    def generate_chat_response(self, text: str, history: Optional[List[Dict]] = None) -> Tuple[str, int, int, float]:
        """Synchronous chat generation (used by legacy /api/evaluate endpoint)."""
        t0 = time.time()
        if not self.gemini_client:
            return "Gemini API key is not configured.", 0, 0, 0.0

        formatted_contents = self.format_gemini_prompt(text, history)
        for model_id in [self.model_name, self.fallback_model]:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_id,
                    contents=formatted_contents,
                )
                latency = round(time.time() - t0, 3)
                ans = response.text or "I have processed your query."
                input_count = len(text.split())
                output_count = len(ans.split())
                return ans, input_count, output_count, latency
            except Exception as e:
                print(f"[TransformerService] Sync generate error on '{model_id}': {e}")

        latency = round(time.time() - t0, 3)
        return "Service temporarily busy. Please retry in a moment.", 0, 0, latency

    def evaluate_text(self, text: str, threshold: float = 0.50, history: Optional[List[Dict]] = None) -> Dict:
        """Complete evaluation pipeline returning unified JSON response."""
        metrics = self.evaluate_tokens(text, threshold)
        answer, in_tok, out_tok, latency = self.generate_chat_response(text, history)

        metrics.update({
            "answer": answer,
            "chatbot_response": answer,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "latency_seconds": latency,
        })
        return metrics

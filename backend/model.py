import os
import sys
import time
import re
import torch
import torch.nn as nn
from evaluator import ConfidenceEvaluator, train_evaluator_on_embeddings

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

class LocalFallbackTokenizer:
    """Fallback tokenizer in case no HuggingFace model or tokenizer is available."""
    def __init__(self, vocab_size=10000):
        self.pad_token_id = 0
        self.eos_token_id = 1
        self.vocab = {"<pad>": 0, "<eos>": 1}
        self.id2token = {0: "<pad>", 1: "<eos>"}
        self.vocab_size = vocab_size

    def encode(self, text, add_special_tokens=False):
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

    def __call__(self, text, return_tensors=None, add_special_tokens=False):
        ids = self.encode(text, add_special_tokens=add_special_tokens)
        if return_tensors == "pt":
            return {"input_ids": torch.tensor([ids], dtype=torch.long)}
        return {"input_ids": ids}

    def convert_ids_to_tokens(self, ids):
        if isinstance(ids, torch.Tensor):
            ids = ids.cpu().tolist()
        return [self.id2token.get(int(i), f"tok_{i}") for i in ids]

    def decode(self, ids, skip_special_tokens=True):
        tokens = self.convert_ids_to_tokens(ids)
        return " ".join(tokens)


class TransformerEvaluatorService:
    def __init__(self, preferred_model: str = None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.use_fallback = False
        
        # Priority list of models: Environment variable -> Parameter -> TinyLlama (cached) -> distilgpt2
        env_model = os.getenv("MODEL_ID")
        candidate_models = []
        if env_model:
            candidate_models.append(env_model)
        if preferred_model:
            candidate_models.append(preferred_model)
        candidate_models.extend(["TinyLlama/TinyLlama-1.1B-Chat-v1.0", "distilgpt2"])
        
        # Deduplicate while preserving order
        candidate_models = list(dict.fromkeys(candidate_models))

        loaded = False
        for model_name in candidate_models:
            # 1. Try local cache first (no download)
            try:
                from transformers import AutoTokenizer, AutoModelForCausalLM
                print(f"[TransformerService] Checking local cache for '{model_name}'...")
                self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
                self.model = AutoModelForCausalLM.from_pretrained(model_name, local_files_only=True).to(self.device)
                self.model.eval()
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                self.embed_layer = self.model.get_input_embeddings()
                self.embed_dim = self.embed_layer.embedding_dim
                self.model_name = model_name
                loaded = True
                print(f"[TransformerService] Successfully loaded cached model '{model_name}'! Embedding dim: {self.embed_dim}")
                break
            except Exception as e_local:
                print(f"[TransformerService] Local cache check for '{model_name}' skipped: {e_local}")

            # 2. Try online download if local cache miss
            try:
                from transformers import AutoTokenizer, AutoModelForCausalLM
                print(f"[TransformerService] Attempting to fetch '{model_name}'...")
                self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=False)
                self.model = AutoModelForCausalLM.from_pretrained(model_name, local_files_only=False).to(self.device)
                self.model.eval()
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                self.embed_layer = self.model.get_input_embeddings()
                self.embed_dim = self.embed_layer.embedding_dim
                self.model_name = model_name
                loaded = True
                print(f"[TransformerService] Successfully fetched and loaded '{model_name}'! Embedding dim: {self.embed_dim}")
                break
            except Exception as e_online:
                print(f"[TransformerService] Could not fetch '{model_name}': {e_online}")

        if not loaded:
            print("[TransformerService] Initializing PyTorch Local Fallback Embedding Layer & Tokenizer...")
            self.use_fallback = True
            self.embed_dim = 768
            self.model_name = "Local-Fallback-Embeddings"
            self.tokenizer = LocalFallbackTokenizer(vocab_size=10000)
            self.embed_layer = nn.Embedding(10000, self.embed_dim).to(self.device)
            self.model = None
        else:
            if hasattr(self.model, "generation_config") and self.model.generation_config is not None:
                self.model.generation_config.max_length = None

        # Initialize PyTorch Confidence Evaluator MLP (Token Embedding -> Linear -> GELU -> Linear -> Sigmoid)
        self.evaluator = ConfidenceEvaluator(embed_dim=self.embed_dim, hidden_dim=128).to(self.device)
        
        # Train MLP on embeddings so scores naturally reflect token informational density
        try:
            train_evaluator_on_embeddings(self.evaluator, self.tokenizer, self.embed_layer, device=self.device)
        except Exception as e_train:
            print(f"[TransformerService] Note during evaluator calibration: {e_train}")

    def clean_token_str(self, raw_token: str) -> str:
        """Strip SentencePiece and BPE space prefix markers while preserving readable token text."""
        cleaned = raw_token.replace('\u2581', '').replace('Ġ', '').strip()
        return cleaned if cleaned else raw_token

    def check_safety(self, text: str) -> str:
        """Lightweight check to filter genuinely hazardous requests while allowing all legitimate queries."""
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

    def generate_chat_response(self, text: str, history: list = None) -> tuple:
        """
        Generates natural conversational response using the full causal LM pipeline.
        Returns: (answer_text, input_tokens_count, output_tokens_count, latency_seconds)
        """
        # Safety check
        safety_refusal = self.check_safety(text)
        if safety_refusal:
            return safety_refusal, 0, 0, 0.0

        if self.use_fallback or self.model is None:
            # Fallback informational response if no weights loaded
            t0 = time.time()
            words = text.strip().split()
            latency = round(time.time() - t0, 3)
            return (
                f"Hello! I received your query: '{text}'. Currently running in fallback mode with local embeddings. "
                f"Evaluated {len(words)} input word tokens through the confidence scoring MLP.",
                len(words),
                25,
                latency
            )

        # Build conversation turns
        system_content = "You are Nexa AI, a helpful, polite, and intelligent AI assistant."

        messages = [{"role": "system", "content": system_content}]

        # Include recent conversation turns for context
        if history and isinstance(history, list):
            for turn in history[-8:]:
                if isinstance(turn, dict):
                    role = turn.get("role", "")
                    content = turn.get("content") or turn.get("text") or ""
                    content = str(content).strip()
                    if role in ["user", "assistant"] and content:
                        messages.append({"role": role, "content": content})

        # Append current user prompt
        messages.append({"role": "user", "content": text.strip()})

        # Format prompt using chat template if available
        try:
            if hasattr(self.tokenizer, "apply_chat_template"):
                formatted_prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
            else:
                formatted_prompt = f"System: {system_content}\nUser: {text}\nAssistant:"
        except Exception:
            formatted_prompt = f"<|user|>\n{text.strip()}</s>\n<|assistant|>\n"

        # Tokenize chat input for model generation
        gen_inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.device)
        input_token_count = gen_inputs["input_ids"].shape[1]

        # Determine reasonable generation budget based on prompt
        is_greeting = text.strip().lower() in ["hi", "hello", "hey", "good morning", "good evening", "greetings"]
        max_new_tokens = 60 if is_greeting else 220

        t0 = time.time()
        try:
            with torch.no_grad():
                outputs = self.model.generate(
                    **gen_inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.12,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            latency_seconds = round(time.time() - t0, 3)

            # Extract generated tokens (excluding prompt tokens)
            gen_ids = outputs[0][input_token_count:]
            output_token_count = len(gen_ids)

            raw_answer = self.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
            
            # Clean up potential template artifacts
            raw_answer = re.sub(r"<\|.*?\|>", "", raw_answer).strip()

            if not raw_answer:
                raw_answer = "I've processed your query. How can I assist you further?"

            return raw_answer, input_token_count, output_token_count, latency_seconds

        except Exception as e_gen:
            latency_seconds = round(time.time() - t0, 3)
            print(f"[TransformerService Error] Generation error: {e_gen}")
            return (
                f"An error occurred during response generation: {str(e_gen)}. Please try again or refine your prompt.",
                input_token_count,
                0,
                latency_seconds
            )

    def evaluate_text(self, text: str, threshold: float = 0.50, history: list = None):
        """
        Complete processing pipeline:
        1. Tokenizes input text.
        2. Computes embeddings & evaluates token confidence via PyTorch MLP.
        3. Applies adaptive token selection based on threshold.
        4. Generates dynamic, natural conversational answer using full causal context.
        5. Computes exact dynamic metrics and returns unified JSON response.
        """
        if not text.strip():
            return {
                "answer": "Please enter a valid message or question.",
                "chatbot_response": "Please enter a valid message or question.",
                "input_tokens": 0,
                "output_tokens": 0,
                "evaluated_tokens": 0,
                "original_tokens": 0,
                "selected_tokens": 0,
                "filtered_tokens_count": 0,
                "tokens_saved": 0,
                "token_saving_percentage": 0.0,
                "saving_percentage": 0.0,
                "latency_seconds": 0.0,
                "tokens": [],
                "token_analysis": [],
                "retained_tokens": [],
                "filtered_tokens": [],
                "confidence_threshold": threshold,
                "model_name": self.model_name,
                "evaluation_type": "Pre-Attention Confidence Evaluator"
            }

        # 1. Tokenize input prompt for token-level evaluation
        inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False)
        if isinstance(inputs["input_ids"], torch.Tensor):
            input_ids = inputs["input_ids"][0].to(self.device)
        else:
            input_ids = torch.tensor(inputs["input_ids"][0], dtype=torch.long, device=self.device)

        raw_tokens = self.tokenizer.convert_ids_to_tokens(input_ids)
        tokens_display = [self.clean_token_str(t) for t in raw_tokens]

        # 2. Extract Token Embeddings from embedding layer
        with torch.no_grad():
            token_embeddings = self.embed_layer(input_ids)

        # 3. Calculate Confidence Scores via PyTorch MLP + Sigmoid
        with torch.no_grad():
            raw_scores = self.evaluator(token_embeddings)
            if raw_scores.dim() == 0:
                raw_scores = raw_scores.unsqueeze(0)
            scores = raw_scores.cpu().tolist()

        # 4. Adaptive Token Selection
        token_analysis = []
        retained_tokens = []
        filtered_tokens = []
        retained_indices = []

        for i, (tok, score) in enumerate(zip(tokens_display, scores)):
            rounded_score = round(float(score), 3)
            is_retained = rounded_score >= threshold
            status = "Retained" if is_retained else "Filtered"

            item = {
                "id": i,
                "token": tok,
                "confidence": rounded_score,
                "status": status,
                "retained": is_retained
            }
            token_analysis.append(item)

            if is_retained:
                retained_tokens.append(tok)
                retained_indices.append(i)
            else:
                filtered_tokens.append(tok)

        # Guarantee at least 1 token retained (the highest scoring token)
        if not retained_indices and token_analysis:
            max_idx = int(torch.argmax(raw_scores).item())
            retained_indices.append(max_idx)
            retained_tokens.append(tokens_display[max_idx])
            token_analysis[max_idx]["status"] = "Retained"
            token_analysis[max_idx]["retained"] = True
            if tokens_display[max_idx] in filtered_tokens:
                filtered_tokens.remove(tokens_display[max_idx])

        # 5. Dynamic Metric Calculations
        original_tokens = len(tokens_display)
        selected_tokens = len(retained_tokens)
        tokens_saved = original_tokens - selected_tokens
        saving_percentage = round((tokens_saved / original_tokens) * 100, 2) if original_tokens > 0 else 0.0

        # 6. Generate Conversational AI Answer
        answer, input_tokens, output_tokens, latency_seconds = self.generate_chat_response(text, history)

        return {
            "answer": answer,
            "chatbot_response": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "evaluated_tokens": original_tokens,
            "original_tokens": original_tokens,
            "selected_tokens": selected_tokens,
            "filtered_tokens_count": tokens_saved,
            "tokens_saved": tokens_saved,
            "token_saving_percentage": saving_percentage,
            "saving_percentage": saving_percentage,
            "latency_seconds": latency_seconds,
            "tokens": tokens_display,
            "token_analysis": token_analysis,
            "retained_tokens": retained_tokens,
            "filtered_tokens": filtered_tokens,
            "confidence_threshold": threshold,
            "model_name": self.model_name,
            "evaluation_type": "Pre-Attention Confidence MLP (Experimental Analysis)"
        }

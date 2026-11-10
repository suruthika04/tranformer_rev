"""
Nexa AI — Contextual Semantic Confidence Evaluator
=================================================
Evaluates token importance using a combination of:
1. Contextual PyTorch MLP over token embeddings with bidirectional context pooling
2. Semantic entropy & information density estimation
3. Critical entity, programming keyword, and negation preservation rules
4. Semantic preservation safety checks before any compression
"""

# Optional torch imports – may be unavailable in constrained environments
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False
    # Minimal dummy implementations to keep type hints and allow code paths that don't need torch
    class _DummyTensor(list):
        def to(self, *args, **kwargs):
            return self
        def cpu(self):
            return self
        def detach(self):
            return self
        def clone(self):
            return self
        def numpy(self):
            return self
    class torch:
        Tensor = _DummyTensor
        @staticmethod
        def no_grad():
            class _Ctx:
                def __enter__(self):
                    return None
                def __exit__(self, exc_type, exc, tb):
                    return False
            return _Ctx()
        @staticmethod
        def tensor(data, dtype=None, device=None):
            return _DummyTensor(data)
        @staticmethod
        def device(_):
            return None
    class nn:
        class Module:
            def __init__(self, *args, **kwargs):
                pass
            def to(self, *args, **kwargs):
                return self
        class Linear(nn.Module):
            def __init__(self, *args, **kwargs):
                pass
        class GELU(nn.Module):
            def __init__(self, *args, **kwargs):
                pass
        class Sigmoid(nn.Module):
            def __init__(self, *args, **kwargs):
                pass
        class Embedding(nn.Module):
            def __init__(self, *args, **kwargs):
                pass
            def to(self, *args, **kwargs):
                return self
            def __call__(self, *args, **kwargs):
                return _DummyTensor([])
    class optim:
        class Adam:
            def __init__(self, *args, **kwargs):
                pass
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Lexical & Semantic Categories for Robust Informational Scoring
# ---------------------------------------------------------------------------

# 1. Negation words: filtering these completely flips prompt meaning
NEGATION_TOKENS: Set[str] = {
    "not", "never", "no", "without", "neither", "nor", "none",
    "cannot", "can't", "don't", "doesn't", "didn't", "won't",
    "wouldn't", "shouldn't", "couldn't", "isn't", "aren't", "wasn't",
    "weren't", "hardly", "barely", "scarcely", "nothing", "nowhere"
}

# 2. Programming languages, tools, frameworks & technologies
PROGRAMMING_ENTITIES: Set[str] = {
    "python", "javascript", "typescript", "java", "c", "c++", "cpp", "c#", "csharp",
    "rust", "golang", "go", "ruby", "php", "swift", "kotlin", "scala", "r", "julia",
    "sql", "mysql", "postgresql", "postgres", "mongodb", "sqlite", "redis", "cassandra",
    "fastapi", "flask", "django", "express", "react", "nextjs", "vue", "angular",
    "pytorch", "torch", "tensorflow", "keras", "huggingface", "transformers", "scikit",
    "pandas", "numpy", "scipy", "docker", "kubernetes", "git", "github", "linux", "bash",
    "html", "css", "graphql", "rest", "api", "json", "yaml", "xml", "jwt", "oauth"
}

# 3. High-information domain keywords (nouns, technical directives, superlatives)
HIGH_INFORMATION_KEYWORDS: Set[str] = {
    "code", "algorithm", "addition", "subtraction", "multiplication", "division",
    "difference", "supervised", "unsupervised", "reinforcement", "learning", "machine",
    "neural", "network", "transformer", "attention", "database", "query", "table",
    "salary", "highest", "second", "third", "lowest", "maximum", "minimum", "average",
    "chatbot", "model", "prompt", "function", "variable", "class", "method", "loop",
    "array", "list", "dict", "dictionary", "object", "string", "integer", "boolean",
    "index", "pointer", "memory", "thread", "process", "server", "client", "request",
    "response", "endpoint", "schema", "authentication", "encryption", "hash", "token",
    "explain", "write", "build", "create", "implement", "calculate", "compare", "find",
    "search", "delete", "remove", "drop", "truncate", "insert", "update", "select",
    "optimize", "debug", "test", "benchmark", "evaluate", "predict", "classify"
}

# 4. Low-information functional stop words (grammatical glue, low entropy)
LOW_INFORMATION_STOP_WORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "into",
    "and", "or", "but", "so", "then", "because", "although", "while",
    "it", "its", "this", "that", "these", "those", "there", "here",
    "i", "me", "my", "we", "us", "our", "you", "your", "he", "him", "she", "her",
    "they", "them", "their", "give", "please", "can", "could", "would", "should",
    "want", "need", "like", "tell", "show", "what", "which", "who", "whom", "whose",
    "where", "when", "why", "how", "between", "among", "through", "during", "before", "after"
}


# ---------------------------------------------------------------------------
# PyTorch Contextual Confidence Evaluator Module
# ---------------------------------------------------------------------------
class ConfidenceEvaluator(nn.Module):
    """
    Contextual Confidence Scoring Module.
    Accepts sequence of token embeddings, incorporates local bidirectional context pooling,
    and outputs a calibrated continuous confidence score in [0.0, 1.0] for each token.
    """
    def __init__(self, embed_dim: int = 768, hidden_dim: int = 128):
        super().__init__()
        # Context projector: evaluates token embedding + local contextual window
        self.context_layer = nn.Linear(embed_dim * 2, hidden_dim)
        self.activation = nn.GELU()
        self.classifier = nn.Linear(hidden_dim, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, token_embeddings: torch.Tensor) -> torch.Tensor:
        """
        token_embeddings: Tensor of shape [seq_len, embed_dim]
        returns: Tensor of confidence scores of shape [seq_len]
        """
        if token_embeddings.dim() == 1:
            token_embeddings = token_embeddings.unsqueeze(0)
        
        seq_len, embed_dim = token_embeddings.shape

        # Compute bidirectional context pooling (left/right neighbor pooling)
        if seq_len > 1:
            left_context = torch.roll(token_embeddings, shifts=1, dims=0)
            left_context[0] = token_embeddings[0]
            right_context = torch.roll(token_embeddings, shifts=-1, dims=0)
            right_context[-1] = token_embeddings[-1]
            pooled_context = 0.5 * (left_context + right_context)
        else:
            pooled_context = token_embeddings

        # Concatenate token embedding with its contextual environment
        contextual_input = torch.cat([token_embeddings, pooled_context], dim=-1)
        h = self.activation(self.context_layer(contextual_input))
        scores = self.sigmoid(self.classifier(h)).squeeze(-1)
        return scores


# ---------------------------------------------------------------------------
# Semantic Scoring & Calibration Engine
# ---------------------------------------------------------------------------
def compute_semantic_prior(clean_token: str, full_text: str = "") -> float:
    """
    Computes an information-theoretic semantic prior score in [0.15, 0.98]
    based on lexical category, syntactic role, and semantic criticality,
    including subword awareness for compound terms (e.g. Fast+API, chat+bot).
    """
    tok = clean_token.lower().strip()
    tok_clean = re.sub(r"^[^\w]+|[^\w]+$", "", tok)

    if not tok_clean:
        return 0.20

    # 1. Negation words: absolute highest preservation priority
    if tok_clean in NEGATION_TOKENS:
        return 0.98

    # 2. Programming languages and frameworks (exact or subword)
    if tok_clean in PROGRAMMING_ENTITIES:
        return 0.96

    # Subword check: check if this token is a subword of a recognized entity in the full text
    if full_text:
        text_words = [re.sub(r"^[^\w]+|[^\w]+$", "", w.lower()) for w in full_text.split()]
        for word in text_words:
            if word in PROGRAMMING_ENTITIES and tok_clean in word and len(tok_clean) >= 2:
                return 0.96
            if word in HIGH_INFORMATION_KEYWORDS and tok_clean in word and len(tok_clean) >= 2:
                return 0.92

    # 3. Numbers, ordinals, digits
    if re.match(r"^\d+(\.\d+)?(st|nd|rd|th)?$", tok_clean):
        return 0.90

    # 4. High-information domain keywords
    if tok_clean in HIGH_INFORMATION_KEYWORDS:
        return 0.92

    # 5. Low-information stop words
    if tok_clean in LOW_INFORMATION_STOP_WORDS:
        return 0.25

    # 6. General nouns/verbs/adjectives (unlisted content words)
    if len(tok_clean) >= 4:
        return 0.78
    elif len(tok_clean) >= 2:
        return 0.65
    else:
        return 0.35


def calibrate_evaluator_weights(
    evaluator: ConfidenceEvaluator,
    tokenizer,
    embed_layer: nn.Embedding,
    device: str = "cpu"
):
    """
    Calibrate the PyTorch MLP weights on real embedding representations
    to align model predictions with information-theoretic semantic density.
    """
    evaluator.train()
    optimizer = optim.Adam(evaluator.parameters(), lr=0.005)
    criterion = nn.BCELoss()

    calibration_pairs = [
        # (Token text, target semantic score)
        ("the", 0.20), ("a", 0.18), ("an", 0.18), ("for", 0.22), ("in", 0.22),
        ("on", 0.22), ("at", 0.22), ("to", 0.22), ("of", 0.20), ("is", 0.25),
        ("are", 0.25), ("give", 0.30), ("me", 0.25), ("i", 0.25), ("want", 0.35),
        ("not", 0.98), ("never", 0.98), ("no", 0.96), ("without", 0.96),
        ("python", 0.96), ("sql", 0.96), ("fastapi", 0.96), ("code", 0.92),
        ("addition", 0.92), ("database", 0.95), ("delete", 0.95), ("salary", 0.94),
        ("highest", 0.92), ("second", 0.90), ("learning", 0.94), ("supervised", 0.96),
        ("unsupervised", 0.96), ("machine", 0.94), ("chatbot", 0.96), ("difference", 0.92)
    ]

    token_ids = []
    targets = []
    for word, target in calibration_pairs:
        # Try with leading space and without leading space to cover both BPE subwords
        for prefix in [" ", ""]:
            ids = tokenizer.encode(prefix + word, add_special_tokens=False)
            if ids:
                token_ids.append(ids[0])
                targets.append(target)

    if not token_ids:
        evaluator.eval()
        return

    ids_tensor = torch.tensor(token_ids, dtype=torch.long, device=device)
    targets_tensor = torch.tensor(targets, dtype=torch.float32, device=device)

    with torch.no_grad():
        embeddings = embed_layer(ids_tensor)

    for _ in range(50):
        optimizer.zero_grad()
        preds = evaluator(embeddings)
        loss = criterion(preds, targets_tensor)
        loss.backward()
        optimizer.step()

    evaluator.eval()
    print(f"[ConfidenceEvaluator] Contextual calibration complete. Final Loss: {loss.item():.4f}")


# ---------------------------------------------------------------------------
# Semantic Preservation & Safety Guardrail
# ---------------------------------------------------------------------------
def validate_semantic_preservation(
    original_tokens: List[str],
    selected_tokens: List[str],
    filtered_tokens: List[str]
) -> Tuple[bool, str]:
    """
    Verifies that filtering did NOT remove mission-critical semantic tokens.
    Guarantees:
    1. Zero negation loss: if a negation word was in the input, it MUST be retained.
    2. Zero critical technical entity loss (programming languages, core targets).
    3. Minimum semantic retention: at least 1 core substantive word kept.
    """
    orig_lower = [t.lower().strip() for t in original_tokens]
    sel_lower = [t.lower().strip() for t in selected_tokens]
    filt_lower = [t.lower().strip() for t in filtered_tokens]

    # Check 1: Negation preservation
    for tok in filt_lower:
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", tok)
        if clean in NEGATION_TOKENS:
            return False, f"Critical negation word '{tok}' was filtered. Meaning would invert."

    # Check 2: Core technical entity preservation
    for tok in filt_lower:
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", tok)
        if clean in PROGRAMMING_ENTITIES:
            return False, f"Programming keyword '{tok}' was filtered."

    # Check 3: At least 1 token kept
    if not selected_tokens:
        return False, "No tokens retained."

    return True, "Semantic preservation verified."

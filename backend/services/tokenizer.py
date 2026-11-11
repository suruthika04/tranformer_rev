"""
Nexa AI — Tokenizer Service
Tokenizes input text into discrete tokens for confidence evaluation.
Uses a lightweight regex-based tokenizer (no heavy model downloads).
"""

import re
from typing import List, Dict


class NexaTokenizer:
    """
    Lightweight tokenizer that splits text into meaningful tokens.
    Uses regex-based word/punctuation splitting suitable for
    confidence evaluation without requiring large model downloads.
    """

    def __init__(self):
        self.vocab: Dict[str, int] = {"<pad>": 0, "<eos>": 1}
        self.id2token: Dict[int, str] = {0: "<pad>", 1: "<eos>"}
        self._next_id = 2

    def tokenize(self, text: str) -> List[str]:
        """Split text into tokens (words and punctuation)."""
        if not text or not text.strip():
            return []
        # Split on word boundaries, keeping punctuation as separate tokens
        tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        return tokens

    def encode(self, text: str) -> List[int]:
        """Tokenize and convert to integer IDs."""
        tokens = self.tokenize(text)
        ids = []
        for token in tokens:
            key = token.lower()
            if key not in self.vocab:
                self.vocab[key] = self._next_id
                self.id2token[self._next_id] = key
                self._next_id += 1
            ids.append(self.vocab[key])
        return ids

    def decode(self, ids: List[int]) -> str:
        """Convert token IDs back to text."""
        tokens = [self.id2token.get(i, f"<unk_{i}>") for i in ids]
        return " ".join(tokens)

    def get_token_count(self, text: str) -> int:
        """Return number of tokens in text."""
        return len(self.tokenize(text))

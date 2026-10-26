import torch
import torch.nn as nn
import torch.optim as optim

class ConfidenceEvaluator(nn.Module):
    """
    Confidence Scoring Module
    Architecture:
    Token Embedding (embed_dim) -> Linear(embed_dim, hidden_dim) -> GELU -> Linear(hidden_dim, 1) -> Sigmoid -> Confidence Score (0..1)
    """
    def __init__(self, embed_dim: int = 2048, hidden_dim: int = 128):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()
        )

    def forward(self, token_embeddings: torch.Tensor) -> torch.Tensor:
        """
        token_embeddings: Tensor of shape [batch_size, seq_len, embed_dim] or [seq_len, embed_dim]
        returns: Tensor of confidence scores between 0 and 1
        """
        # Ensure input dtype matches MLP weights (handles bfloat16/float16 embeddings)
        float_embeddings = token_embeddings.to(dtype=self.mlp[0].weight.dtype)
        scores = self.mlp(float_embeddings).squeeze(-1)
        if scores.dim() == 0:
            scores = scores.unsqueeze(0)
        return scores


def train_evaluator_on_embeddings(evaluator: ConfidenceEvaluator, tokenizer, embedding_layer, device="cpu"):
    """
    Trains the ConfidenceEvaluator MLP on token embeddings using PyTorch Adam & BCELoss
    so that structural/stop tokens produce lower confidence and content tokens produce higher confidence.
    """
    evaluator.train()
    optimizer = optim.Adam(evaluator.parameters(), lr=0.01)
    criterion = nn.BCELoss()

    # Representative stop words and structural tokens (lower informational entropy)
    stop_words = [
        "the", "a", "an", "is", "are", "was", "were", "on", "in", "at", "to", "for", 
        "of", "and", "or", "because", "it", "with", "by", ".", ",", "!", "?", "that",
        "this", "from", "be", "as", "at", "so", "if", "then"
    ]
    
    # Representative semantic content words (higher informational density)
    content_words = [
        "cat", "dog", "sleeping", "mat", "tired", "running", "computer", "transformer", 
        "model", "evaluator", "confidence", "attention", "token", "code", "neural", 
        "python", "project", "academic", "student", "study", "intelligence", "algorithm",
        "learning", "data", "software", "network", "program", "function", "variable"
    ]

    stop_ids = []
    for w in stop_words:
        ids = tokenizer.encode(w, add_special_tokens=False)
        if ids:
            stop_ids.append(ids[0])

    content_ids = []
    for w in content_words:
        ids = tokenizer.encode(w, add_special_tokens=False)
        if ids:
            content_ids.append(ids[0])

    if not stop_ids or not content_ids:
        evaluator.eval()
        return

    stop_tensors = torch.tensor(stop_ids, dtype=torch.long, device=device)
    content_tensors = torch.tensor(content_ids, dtype=torch.long, device=device)

    with torch.no_grad():
        stop_embeds = embedding_layer(stop_tensors)
        content_embeds = embedding_layer(content_tensors)

    stop_targets = torch.full((len(stop_ids),), 0.22, dtype=torch.float32, device=device)
    content_targets = torch.full((len(content_ids),), 0.88, dtype=torch.float32, device=device)

    all_embeds = torch.cat([stop_embeds, content_embeds], dim=0)
    all_targets = torch.cat([stop_targets, content_targets], dim=0)

    for _ in range(40):
        optimizer.zero_grad()
        preds = evaluator(all_embeds)
        loss = criterion(preds, all_targets)
        loss.backward()
        optimizer.step()

    evaluator.eval()
    print(f"[ConfidenceEvaluator] Calibrated MLP on embeddings. Loss: {loss.item():.4f}")

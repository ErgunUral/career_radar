from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer


class TextEmbedder:
    def encode(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class HashingTextEmbedder(TextEmbedder):
    def __init__(self, n_features: int = 1024) -> None:
        self.vectorizer = HashingVectorizer(
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
            ngram_range=(1, 2),
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        matrix = self.vectorizer.transform(texts)
        return matrix.astype(np.float32).toarray()


class SentenceTransformerTextEmbedder(TextEmbedder):
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(embeddings, dtype=np.float32)


def create_embedder(
    model_name: str, prefer_sentence_transformer: bool = False
) -> TextEmbedder:
    if prefer_sentence_transformer:
        try:
            return SentenceTransformerTextEmbedder(model_name=model_name)
        except Exception:
            logging.warning(
                "BLE001 embedding: SentenceTransformer %s yüklenemedi, HashingTextEmbedder fallback kullanıldı",
                model_name,
            )
            return HashingTextEmbedder()
    return HashingTextEmbedder()


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    left_norm = left / np.clip(np.linalg.norm(left, axis=1, keepdims=True), 1e-9, None)
    right_norm = right / np.clip(
        np.linalg.norm(right, axis=1, keepdims=True), 1e-9, None
    )
    return left_norm @ right_norm.T


@dataclass
class VectorHit:
    index: int
    similarity: float


class InMemoryVectorIndex:
    def __init__(self, embeddings: np.ndarray) -> None:
        self.embeddings = embeddings

    def query(self, query_embedding: np.ndarray, top_k: int) -> list[VectorHit]:
        scores = cosine_similarity(query_embedding.reshape(1, -1), self.embeddings)[0]
        best_indices = np.argsort(scores)[::-1][:top_k]
        return [
            VectorHit(index=int(index), similarity=float(scores[index]))
            for index in best_indices
        ]

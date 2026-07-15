"""Evidence-grounded question answering backed by a local Ollama model.

The agent never asks the LLM to compute repository statistics. Deterministic
metrics are computed in :mod:`src.analytics` and retrieved evidence is gathered
by :mod:`src.retrieval`; the model's only job is to phrase an answer that is
strictly supported by the supplied context. This mirrors the Checkpoint 1
design principle of separating deterministic computation from LLM interpretation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from httpx import TimeoutException
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import Repository
from src.retrieval.corpus import EvidenceChunk, SemanticRetriever

logger = logging.getLogger(__name__)

GROUNDING_SYSTEM_PROMPT = (
    "You are RepoSense, a GitHub repository intelligence assistant. Answer the "
    "user's question using ONLY the numbered evidence and the precomputed metrics "
    "provided below. Cite the evidence you rely on by its number (e.g. [2]). If the "
    "provided context does not contain the answer, reply that the evidence is "
    "insufficient. Never invent repository names, numbers, or metrics that are not "
    "present in the context."
)


@dataclass
class GroundedAnswer:
    question: str
    answer: str
    evidence: list[EvidenceChunk] = field(default_factory=list)


def format_evidence(chunks: list[EvidenceChunk], *, max_chars: int = 800) -> str:
    if not chunks:
        return "(no retrieved evidence)"
    blocks: list[str] = []
    for position, chunk in enumerate(chunks, start=1):
        snippet = chunk.text.strip().replace("\r\n", "\n")
        if len(snippet) > max_chars:
            snippet = snippet[:max_chars].rstrip() + "…"
        blocks.append(
            f"[{position}] ({chunk.repository_full_name} · {chunk.source_type} "
            f"{chunk.source_id}) {chunk.title}\n{snippet}"
        )
    return "\n\n".join(blocks)


def build_grounded_prompt(
    question: str,
    chunks: list[EvidenceChunk],
    *,
    metrics_context: str | None = None,
    max_evidence_chars: int = 800,
) -> str:
    """Assemble the user-turn prompt from evidence and optional metric context."""
    sections = [
        f"Question: {question}",
        "",
        "Retrieved evidence:",
        format_evidence(chunks, max_chars=max_evidence_chars),
    ]
    if metrics_context:
        sections += ["", "Precomputed metrics:", metrics_context]
    sections += ["", "Answer using only the context above and cite evidence by number."]
    return "\n".join(sections)


class OllamaClient:
    """Minimal HTTP client for the Ollama chat API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.model = self.settings.ollama_model

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "num_predict": self.settings.ollama_num_predict,
                "temperature": 0.2,
            },
        }
        timeout = httpx.Timeout(
            self.settings.ollama_request_timeout,
            connect=10.0,
        )
        with httpx.Client(timeout=timeout) as client:
            try:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
            except TimeoutException as exc:
                raise TimeoutError(
                    f"Ollama did not finish within {self.settings.ollama_request_timeout:.0f}s "
                    f"using model {self.model!r}."
                ) from exc
            data = response.json()
        return (data.get("message") or {}).get("content", "")


def check_ollama_available(settings: Settings | None = None) -> None:
    """Raise a clear error if Ollama is unreachable or the model is missing."""
    settings = settings or get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            models = {item.get("name") for item in response.json().get("models", [])}
    except httpx.ConnectError as exc:
        raise ConnectionError(
            f"Cannot connect to Ollama at {base_url}. Start it with `ollama serve`."
        ) from exc
    except TimeoutException as exc:
        raise TimeoutError(
            f"Ollama at {base_url} did not respond within 10 seconds."
        ) from exc

    if settings.ollama_model not in models:
        raise ValueError(
            f"Model {settings.ollama_model!r} is not available. "
            f"Run `ollama pull {settings.ollama_model}`."
        )


class GroundedChatAgent:
    """Retrieve evidence, then ask the local model to answer over it."""

    def __init__(
        self,
        session: Session,
        *,
        repository: Repository | None = None,
        settings: Settings | None = None,
        client: OllamaClient | None = None,
        retriever: SemanticRetriever | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or OllamaClient(self.settings)
        self.retriever = retriever or SemanticRetriever.from_session(session, repository)

    def answer(
        self,
        question: str,
        *,
        top_k: int | None = None,
        metrics_context: str | None = None,
    ) -> GroundedAnswer:
        k = top_k or self.settings.retrieval_top_k
        chunks = self.retriever.search(question, top_k=k)
        prompt = build_grounded_prompt(
            question,
            chunks,
            metrics_context=metrics_context,
            max_evidence_chars=self.settings.retrieval_evidence_max_chars,
        )
        text = self.client.chat(GROUNDING_SYSTEM_PROMPT, prompt)
        return GroundedAnswer(question=question, answer=text, evidence=chunks)

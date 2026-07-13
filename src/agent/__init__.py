"""Evidence-grounded chat over a local Ollama model (Checkpoint 3)."""

from src.agent.grounded_chat import (
    GroundedAnswer,
    GroundedChatAgent,
    OllamaClient,
    build_grounded_prompt,
    format_evidence,
)

__all__ = [
    "GroundedAnswer",
    "GroundedChatAgent",
    "OllamaClient",
    "build_grounded_prompt",
    "format_evidence",
]

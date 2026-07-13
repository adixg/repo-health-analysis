from src.agent.grounded_chat import (
    GroundedChatAgent,
    build_grounded_prompt,
    format_evidence,
)
from src.retrieval.corpus import EvidenceChunk


def _chunk(source_id: str, title: str, text: str) -> EvidenceChunk:
    return EvidenceChunk(
        repository_full_name="psf/requests",
        source_type="issue",
        source_id=source_id,
        title=title,
        text=text,
        url=None,
        score=0.5,
    )


def test_format_evidence_numbers_and_labels_chunks() -> None:
    rendered = format_evidence([_chunk("1", "SSL error", "certificate verification fails")])
    assert "[1]" in rendered
    assert "psf/requests" in rendered
    assert "certificate verification fails" in rendered


def test_format_evidence_empty() -> None:
    assert format_evidence([]) == "(no retrieved evidence)"


def test_build_grounded_prompt_includes_question_and_evidence() -> None:
    prompt = build_grounded_prompt(
        "Why do SSL errors occur?",
        [_chunk("1", "SSL error", "certificate verification fails on handshake")],
        metrics_context="closure_rate=0.8",
    )
    assert "Why do SSL errors occur?" in prompt
    assert "certificate verification fails on handshake" in prompt
    assert "closure_rate=0.8" in prompt
    assert "cite evidence by number" in prompt


class _FakeRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def search(self, query, top_k=5):
        return self._chunks


class _FakeOllama:
    def __init__(self):
        self.last_user_prompt = None

    def chat(self, system_prompt, user_prompt):
        self.last_user_prompt = user_prompt
        return "The SSL error is caused by certificate verification. [1]"


def test_grounded_chat_agent_grounds_answer_in_evidence() -> None:
    chunks = [_chunk("1", "SSL error", "certificate verification fails on handshake")]
    fake_client = _FakeOllama()
    agent = GroundedChatAgent(
        session=None,
        client=fake_client,
        retriever=_FakeRetriever(chunks),
    )

    result = agent.answer("Why do SSL errors occur?", top_k=3)

    assert result.evidence == chunks
    assert "[1]" in result.answer
    assert "certificate verification fails on handshake" in fake_client.last_user_prompt

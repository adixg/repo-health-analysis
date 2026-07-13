from src.retrieval.corpus import EvidenceChunk, SemanticRetriever
from src.retrieval.tfidf import TfidfIndex, tokenize


def test_tokenize_splits_on_non_alphanumeric() -> None:
    assert tokenize("Rate-limit handling, retries!") == [
        "rate",
        "limit",
        "handling",
        "retries",
    ]


def test_tfidf_index_ranks_matching_document_first() -> None:
    index = TfidfIndex().fit(
        [
            "authentication token rate limit handling for the github api",
            "streamlit dashboard layout and plotting of commit trends",
            "postgresql schema migrations and sqlalchemy models",
        ]
    )
    results = index.query("github api rate limit token", top_k=3)
    assert results, "expected at least one match"
    assert results[0][0] == 0
    assert results[0][1] > 0.0


def test_semantic_retriever_returns_scored_chunks() -> None:
    chunks = [
        EvidenceChunk(
            repository_full_name="psf/requests",
            source_type="issue",
            source_id="1",
            title="SSL verification error",
            text="requests raises an SSL certificate verification error on handshake",
            url=None,
        ),
        EvidenceChunk(
            repository_full_name="psf/requests",
            source_type="issue",
            source_id="2",
            title="Add retry adapter",
            text="feature request to add a configurable retry adapter for connections",
            url=None,
        ),
    ]
    retriever = SemanticRetriever(chunks)
    results = retriever.search("ssl certificate verification", top_k=2)
    assert results
    assert results[0].source_id == "1"
    assert results[0].score > 0.0


def test_semantic_retriever_empty_corpus_returns_empty() -> None:
    retriever = SemanticRetriever([])
    assert retriever.search("anything") == []

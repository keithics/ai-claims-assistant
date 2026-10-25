from rag import RetrievedChunk, estimate_tokens, trim_chunks


def chunk(i: int, text: str, doc: str = "d") -> RetrievedChunk:
    return RetrievedChunk(f"{doc}-{i}", doc, "T", "H", text, "ph", "en", i, 1.0)


A = "Report the incident to us within 30 days of the incident and send documents"
B = "Approved claims are paid within fifteen working days after we receive complete documents"
C = "A waiting period of thirty days applies to new health policies except for accidents"


def test_everything_is_kept_when_it_fits() -> None:
    result = trim_chunks([chunk(1, A), chunk(2, B)], max_chunks=3, max_tokens=500)
    assert [c.id for c in result.chunks] == ["d-1", "d-2"] and not result.changed


def test_near_duplicates_are_dropped() -> None:
    overlapping = A + " promptly"
    result = trim_chunks(
        [chunk(1, A), chunk(2, overlapping), chunk(3, B)], max_chunks=3, max_tokens=500
    )
    assert [c.id for c in result.chunks] == ["d-1", "d-3"]
    assert result.dropped_duplicates == 1 and result.changed


def test_duplicates_can_be_kept_when_dedupe_is_off() -> None:
    result = trim_chunks([chunk(1, A), chunk(2, A)], max_chunks=3, max_tokens=500, dedupe=False)
    assert len(result.chunks) == 2


def test_the_chunk_count_and_the_token_budget_both_limit_the_result() -> None:
    chunks = [chunk(1, A), chunk(2, B), chunk(3, C)]
    assert len(trim_chunks(chunks, max_chunks=2, max_tokens=500).chunks) == 2
    budget = estimate_tokens(A) + 1
    result = trim_chunks(chunks, max_chunks=3, max_tokens=budget)
    assert [c.id for c in result.chunks] == ["d-1"] and result.dropped_over_budget == 2


def test_the_best_chunk_is_always_kept_even_if_it_alone_exceeds_the_budget() -> None:
    result = trim_chunks([chunk(1, A)], max_chunks=3, max_tokens=1)
    assert [c.id for c in result.chunks] == ["d-1"]


def test_nothing_in_nothing_out() -> None:
    assert trim_chunks([], max_chunks=3, max_tokens=100).chunks == []

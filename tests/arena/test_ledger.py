"""Append-only JSONL ledger with a SHA-256 hash chain; any edit, deletion, insertion or reorder is detected."""

import json

import pytest

from arena.ledger import GENESIS, Ledger, LedgerError


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "ledger.jsonl")
    for i in range(4):
        lg.append({"type": "decision", "ticker": f"T{i}", "label": "Hold"})
    return lg


def lines(lg):
    return lg.path.read_text(encoding="utf-8").splitlines()


def write(lg, ls):
    lg.path.write_text("\n".join(ls) + "\n", encoding="utf-8")


def test_chain_links_and_verifies(ledger):
    recs = ledger.records()
    assert [r["seq"] for r in recs] == [0, 1, 2, 3]
    assert recs[0]["prev"] == GENESIS
    assert all(recs[i]["prev"] == recs[i - 1]["hash"] for i in range(1, 4))
    assert ledger.verify() == recs[-1]["hash"] == ledger.head()


def test_edited_field_is_detected(ledger):
    ls = lines(ledger)
    rec = json.loads(ls[1]); rec["label"] = "Buy"; ls[1] = json.dumps(rec)
    write(ledger, ls)
    with pytest.raises(LedgerError, match="seq 1"):
        ledger.verify()


def test_edit_with_recomputed_hash_breaks_the_next_link(ledger):
    ls = lines(ledger)
    rec = json.loads(ls[1]); rec["label"] = "Buy"; rec.pop("hash")
    from arena.ledger import record_hash
    rec["hash"] = record_hash(rec); ls[1] = json.dumps(rec)
    write(ledger, ls)
    with pytest.raises(LedgerError, match="seq 2"):
        ledger.verify()


@pytest.mark.parametrize("mutate", [
    lambda ls: ls[:1] + ls[2:],             # delete a middle record
    lambda ls: [ls[0], ls[2], ls[1], ls[3]],  # reorder
    lambda ls: ls[:2] + [ls[1]] + ls[2:],   # duplicate / insert
])
def test_structural_tampering_is_detected(ledger, mutate):
    write(ledger, mutate(lines(ledger)))
    with pytest.raises(LedgerError):
        ledger.verify()


def test_truncated_tail_is_caught_by_the_published_head(ledger):
    published = ledger.head()
    write(ledger, lines(ledger)[:-1])
    ledger.verify()  # the chain itself is still consistent
    with pytest.raises(LedgerError, match="head"):
        ledger.verify(expected_head=published)


def test_append_refuses_a_tampered_ledger(ledger):
    write(ledger, lines(ledger)[1:])
    with pytest.raises(LedgerError):
        ledger.append({"type": "decision"})


def test_reserved_keys_are_rejected(tmp_path):
    lg = Ledger(tmp_path / "l.jsonl")
    for key in ("seq", "prev", "hash"):
        with pytest.raises(ValueError):
            lg.append({key: 1})


def test_empty_ledger_head_is_genesis(tmp_path):
    lg = Ledger(tmp_path / "l.jsonl")
    assert lg.records() == [] and lg.head() == GENESIS and lg.verify() == GENESIS

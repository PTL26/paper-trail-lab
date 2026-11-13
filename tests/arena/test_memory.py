"""Section 7: A's memory file is decrypted for a run, re-encrypted after, and never left in plaintext."""

import pytest

from arena.crypto import decrypt_bytes, generate_identity
from arena.memory import KEY_ENV, MemoryVault, secret_from_env


@pytest.fixture
def key():
    return generate_identity()[0]


def test_first_run_starts_empty_and_saves_encrypted(tmp_path, key):
    enc = tmp_path / "repo" / "memory.md.age"
    vault = MemoryVault(enc, key)
    with vault.open(tmp_path / "work") as plain:
        assert not plain.exists()
        plain.write_text("## AAPL 2026-11-30 Buy\n")
    assert not plain.exists()
    assert b"AAPL" not in enc.read_bytes()
    assert decrypt_bytes(enc.read_bytes(), key) == b"## AAPL 2026-11-30 Buy\n"


def test_second_run_reads_back_and_appends(tmp_path, key):
    enc = tmp_path / "memory.md.age"
    vault = MemoryVault(enc, key)
    with vault.open(tmp_path / "w1") as p:
        p.write_text("one\n")
    with vault.open(tmp_path / "w2") as p:
        assert p.read_text() == "one\n"
        p.write_text(p.read_text() + "two\n")
    assert decrypt_bytes(enc.read_bytes(), key) == b"one\ntwo\n"


def test_saved_even_if_the_run_raises_and_plaintext_removed(tmp_path, key):
    enc = tmp_path / "memory.md.age"
    with pytest.raises(RuntimeError):
        with MemoryVault(enc, key).open(tmp_path / "w") as p:
            p.write_text("partial\n")
            raise RuntimeError("boom")
    assert not p.exists() and decrypt_bytes(enc.read_bytes(), key) == b"partial\n"


def test_missing_file_after_first_run_is_an_error(tmp_path, key):
    with pytest.raises(FileNotFoundError):
        with MemoryVault(tmp_path / "gone.age", key, must_exist=True).open(tmp_path / "w"):
            pass


def test_wrong_key_fails_before_the_run(tmp_path, key):
    enc = tmp_path / "memory.md.age"
    with MemoryVault(enc, key).open(tmp_path / "w") as p:
        p.write_text("x")
    with pytest.raises(Exception):
        with MemoryVault(enc, generate_identity()[0]).open(tmp_path / "w2"):
            pass
    assert decrypt_bytes(enc.read_bytes(), key) == b"x"  # untouched


def test_secret_from_env(key):
    assert secret_from_env({KEY_ENV: key}) == key
    with pytest.raises(KeyError, match=KEY_ENV):
        secret_from_env({})
    with pytest.raises(ValueError):
        secret_from_env({KEY_ENV: "not-a-key"})

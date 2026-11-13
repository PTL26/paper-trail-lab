"""The agent memory file is carried between runs encrypted with age (draft section 7)."""

import pytest

from arena.crypto import decrypt_bytes, encrypt_bytes, generate_identity

PLAIN = b"## 2026-11-27 AAPL Buy\nrealised return ...\n"


def test_round_trip_and_standard_age_format():
    secret, recipient = generate_identity()
    assert secret.startswith("AGE-SECRET-KEY-1") and recipient.startswith("age1")
    blob = encrypt_bytes(PLAIN, recipient)
    assert blob.startswith(b"age-encryption.org/v1\n")
    assert PLAIN not in blob and b"AAPL" not in blob
    assert decrypt_bytes(blob, secret) == PLAIN


def test_wrong_key_fails():
    _, recipient = generate_identity()
    other, _ = generate_identity()
    with pytest.raises(Exception):
        decrypt_bytes(encrypt_bytes(PLAIN, recipient), other)


def test_recipient_is_derived_from_the_secret():
    from arena.crypto import recipient_for
    secret, recipient = generate_identity()
    assert recipient_for(secret) == recipient

"""age encryption for the agent memory file carried in the public repo (section 7)."""

from __future__ import annotations

from typing import Tuple

import pyrage
from pyrage import x25519


def generate_identity() -> Tuple[str, str]:
    """(secret key 'AGE-SECRET-KEY-1...', recipient 'age1...')."""
    ident = x25519.Identity.generate()
    return str(ident), str(ident.to_public())


def recipient_for(secret: str) -> str:
    return str(x25519.Identity.from_str(secret).to_public())


def encrypt_bytes(data: bytes, recipient: str) -> bytes:
    return pyrage.encrypt(data, [x25519.Recipient.from_str(recipient)])


def decrypt_bytes(blob: bytes, secret: str) -> bytes:
    return pyrage.decrypt(blob, [x25519.Identity.from_str(secret)])

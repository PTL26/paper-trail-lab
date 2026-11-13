"""Section 7: A's memory file travels between runs encrypted with age in the public repo.

For a run, the file is decrypted into a private working directory where TradingAgents reads and
updates it (`memory_log_path`); afterwards it is re-encrypted over the repo copy and the plaintext is
deleted. TradingAgents itself settles past decisions (realised return over its holding period) and
writes the lessons into this file, so carrying the file is what feeds the returns back."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping

from .crypto import decrypt_bytes, encrypt_bytes, recipient_for

KEY_ENV = "ARENA_AGE_KEY"
PLAIN_NAME = "trading_memory.md"


def secret_from_env(env: Mapping[str, str] = os.environ) -> str:
    if not env.get(KEY_ENV):
        raise KeyError(f"{KEY_ENV} is not set")
    secret = env[KEY_ENV].strip()
    if not secret.startswith("AGE-SECRET-KEY-1"):
        raise ValueError(f"{KEY_ENV} is not an age secret key")
    recipient_for(secret)  # raises on a malformed key
    return secret


class MemoryVault:
    def __init__(self, encrypted_path, secret: str, must_exist: bool = False, plain_name: str = PLAIN_NAME):
        self.path, self.secret, self.must_exist = Path(encrypted_path), secret, must_exist
        self.plain_name = plain_name

    def _save(self, plain: Path) -> None:
        if not plain.exists():
            return
        blob = encrypt_bytes(plain.read_bytes(), recipient_for(self.secret))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, self.path)

    @contextmanager
    def open(self, workdir):
        """Yields the plaintext path for TradingAgents' `memory_log_path`."""
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        plain = workdir / self.plain_name
        if self.path.exists():
            data = decrypt_bytes(self.path.read_bytes(), self.secret)  # wrong key: fails before the run
            fd = os.open(plain, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        elif self.must_exist:
            raise FileNotFoundError(self.path)
        try:
            yield plain
        finally:
            try:
                self._save(plain)  # A's memory as A left it, even after a failed run
            finally:
                if plain.exists():
                    plain.unlink()


EncryptedFile = MemoryVault  # the same mechanism carries the ledger

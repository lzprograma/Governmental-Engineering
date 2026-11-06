"""Cofre local para credenciais de API.

A chave mestra fica em arquivo separado, com permissões restritas. Para instalações
mais fortes, defina LUNZ_VAULT_KEY a partir de um secret manager/KMS externo.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken


class VaultError(RuntimeError):
    pass


class SecretVault:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        env_key = os.getenv("LUNZ_VAULT_KEY")
        key_path = self.data_dir / ".lunz_vault.key"
        if env_key:
            key = env_key.encode("ascii")
        else:
            if key_path.exists():
                key = key_path.read_bytes().strip()
            else:
                key = Fernet.generate_key()
                fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(key + b"\n")
                try:
                    os.chmod(key_path, 0o600)
                except OSError:
                    pass
        try:
            self._fernet = Fernet(key)
        except Exception as exc:
            raise VaultError("Chave do cofre inválida. Verifique LUNZ_VAULT_KEY ou .lunz_vault.key.") from exc

    def encrypt(self, secret: str | None) -> str | None:
        if not secret:
            return None
        return self._fernet.encrypt(secret.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str | None) -> str | None:
        if not token:
            return None
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeError) as exc:
            raise VaultError("Não foi possível abrir a credencial. A chave mestra pode ter mudado.") from exc

    @staticmethod
    def key_file_warning() -> str:
        return (
            "O cofre cifra chaves em repouso, mas a chave mestra local também precisa ser protegida. "
            "Para produção, use LUNZ_VAULT_KEY fornecida por um secret manager/KMS e controle o acesso ao host."
        )

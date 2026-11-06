"""Persistência SQLite de conexões de API, cidadãos-modelo e conversas."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .vault import SecretVault


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegistryError(RuntimeError):
    pass


SENSITIVE_HEADER_FRAGMENTS = ("authorization", "api-key", "apikey", "token", "secret", "cookie", "credential")


def validate_extra_headers(headers: dict[str, Any]) -> None:
    if not isinstance(headers, dict):
        raise ValueError("Cabeçalhos adicionais precisam ser um objeto JSON.")
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("Cabeçalhos adicionais devem conter apenas texto.")
        lowered = name.lower().replace("_", "-")
        if any(fragment in lowered for fragment in SENSITIVE_HEADER_FRAGMENTS):
            raise ValueError(f"O cabeçalho '{name}' parece conter credencial. Use o campo Chave API, que é cifrado.")
        if "\n" in name + value or "\r" in name + value:
            raise ValueError("Quebras de linha não são permitidas em cabeçalhos HTTP.")


class NationRegistry:
    def __init__(self, db_path: Path, data_dir: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vault = SecretVault(data_dir)
        self._init_db()
        try:
            self.db_path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS api_connections (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              provider_type TEXT NOT NULL,
              api_format TEXT NOT NULL,
              base_url TEXT NOT NULL,
              auth_mode TEXT NOT NULL DEFAULT 'bearer',
              api_key_encrypted TEXT,
              api_key_header TEXT,
              extra_headers_json TEXT NOT NULL DEFAULT '{}',
              timeout_seconds REAL NOT NULL DEFAULT 45,
              allow_private_network INTEGER NOT NULL DEFAULT 0,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS citizens (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              model_id TEXT NOT NULL,
              connection_id TEXT NOT NULL REFERENCES api_connections(id) ON DELETE RESTRICT,
              role TEXT NOT NULL DEFAULT 'Cidadão',
              system_prompt TEXT NOT NULL DEFAULT '',
              avatar TEXT NOT NULL DEFAULT '🤖',
              temperature REAL NOT NULL DEFAULT 0.3,
              max_tokens INTEGER NOT NULL DEFAULT 1200,
              status TEXT NOT NULL DEFAULT 'active',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS citizen_messages (
              id TEXT PRIMARY KEY,
              citizen_id TEXT NOT NULL REFERENCES citizens(id) ON DELETE CASCADE,
              role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
              content TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_citizen_time ON citizen_messages(citizen_id, created_at);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(api_connections)").fetchall()}
            if "allow_private_network" not in columns:
                db.execute("ALTER TABLE api_connections ADD COLUMN allow_private_network INTEGER NOT NULL DEFAULT 0")

    def create_connection(self, data: dict[str, Any]) -> dict[str, Any]:
        connection_id = str(uuid4())
        timestamp = now()
        extra_headers = data.get("extra_headers") or {}
        validate_extra_headers(extra_headers)
        encrypted = self.vault.encrypt(data.get("api_key"))
        with self._connect() as db:
            db.execute("""INSERT INTO api_connections
                (id,name,provider_type,api_format,base_url,auth_mode,api_key_encrypted,api_key_header,
                 extra_headers_json,timeout_seconds,allow_private_network,enabled,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (connection_id, data["name"], data["provider_type"], data["api_format"],
                 data["base_url"].rstrip("/"), data.get("auth_mode", "bearer"), encrypted,
                 data.get("api_key_header"), json.dumps(extra_headers),
                 float(data.get("timeout_seconds", 45)), int(bool(data.get("allow_private_network", False))),
                 1, timestamp, timestamp))
        return self.get_connection(connection_id)

    def get_connection(self, connection_id: str, include_secret: bool = False) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM api_connections WHERE id=?", (connection_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["enabled"] = bool(item["enabled"])
        item["allow_private_network"] = bool(item.get("allow_private_network", 0))
        item["extra_headers"] = json.loads(item.pop("extra_headers_json"))
        encrypted = item.pop("api_key_encrypted")
        item["has_api_key"] = bool(encrypted)
        if include_secret:
            item["api_key"] = self.vault.decrypt(encrypted)
        return item

    def list_connections(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id FROM api_connections ORDER BY created_at DESC").fetchall()
        return [self.get_connection(row["id"]) for row in rows]

    def update_connection(self, connection_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "provider_type", "api_format", "base_url", "auth_mode", "api_key",
                   "api_key_header", "extra_headers", "timeout_seconds", "allow_private_network", "enabled"}
        updates = {key: value for key, value in changes.items() if key in allowed}
        if not updates:
            existing = self.get_connection(connection_id)
            if not existing:
                raise KeyError("Conexão não encontrada.")
            return existing
        if "api_key" in updates:
            updates["api_key_encrypted"] = self.vault.encrypt(updates.pop("api_key"))
        if "base_url" in updates:
            updates["base_url"] = str(updates["base_url"]).rstrip("/")
        if "extra_headers" in updates:
            validate_extra_headers(updates["extra_headers"])
            updates["extra_headers_json"] = json.dumps(updates.pop("extra_headers"))
        if "enabled" in updates:
            updates["enabled"] = int(bool(updates["enabled"]))
        if "allow_private_network" in updates:
            updates["allow_private_network"] = int(bool(updates["allow_private_network"]))
        updates["updated_at"] = now()
        assignments = ", ".join(f"{key}=?" for key in updates)
        with self._connect() as db:
            cursor = db.execute(f"UPDATE api_connections SET {assignments} WHERE id=?",
                                (*updates.values(), connection_id))
            if not cursor.rowcount:
                raise KeyError("Conexão não encontrada.")
        return self.get_connection(connection_id)

    def delete_connection(self, connection_id: str) -> None:
        with self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM citizens WHERE connection_id=?", (connection_id,)).fetchone()[0]
            if count:
                raise RegistryError("Esta conexão está vinculada a cidadãos. Reatribua ou exclua os cidadãos antes.")
            cursor = db.execute("DELETE FROM api_connections WHERE id=?", (connection_id,))
            if cursor.rowcount == 0:
                raise KeyError("Conexão não encontrada.")

    def create_citizen(self, data: dict[str, Any]) -> dict[str, Any]:
        connection = self.get_connection(data["connection_id"])
        if not connection:
            raise ValueError("Conexão de API não encontrada.")
        if not connection["enabled"]:
            raise ValueError("A conexão selecionada está desativada.")
        citizen_id, timestamp = str(uuid4()), now()
        with self._connect() as db:
            db.execute("""INSERT INTO citizens
              (id,name,model_id,connection_id,role,system_prompt,avatar,temperature,max_tokens,status,created_at,updated_at)
              VALUES (?,?,?,?,?,?,?,?,?,'active',?,?)""",
              (citizen_id, data["name"], data["model_id"], data["connection_id"],
               data.get("role", "Cidadão"), data.get("system_prompt", ""), data.get("avatar", "🤖"),
               float(data.get("temperature", 0.3)), int(data.get("max_tokens", 1200)), timestamp, timestamp))
        return self.get_citizen(citizen_id)

    def get_citizen(self, citizen_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("""SELECT c.*, a.name AS connection_name, a.provider_type, a.api_format
                FROM citizens c JOIN api_connections a ON a.id=c.connection_id WHERE c.id=?""", (citizen_id,)).fetchone()
        return dict(row) if row else None

    def list_citizens(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id FROM citizens ORDER BY created_at DESC").fetchall()
        return [self.get_citizen(row["id"]) for row in rows]

    def update_citizen(self, citizen_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "model_id", "connection_id", "role", "system_prompt", "avatar", "temperature", "max_tokens"}
        updates = {key: value for key, value in changes.items() if key in allowed}
        if not updates:
            existing = self.get_citizen(citizen_id)
            if not existing:
                raise KeyError("Cidadão não encontrado.")
            return existing
        if "connection_id" in updates:
            connection = self.get_connection(str(updates["connection_id"]))
            if not connection or not connection["enabled"]:
                raise ValueError("Conexão de API não encontrada ou desativada.")
        assignments = ", ".join(f"{key}=?" for key in updates)
        updates["updated_at"] = now()
        with self._connect() as db:
            cursor = db.execute(f"UPDATE citizens SET {assignments}, updated_at=? WHERE id=?",
                                (*[v for k, v in updates.items() if k != "updated_at"], updates["updated_at"], citizen_id))
            if not cursor.rowcount:
                raise KeyError("Cidadão não encontrado.")
        return self.get_citizen(citizen_id)

    def update_citizen_status(self, citizen_id: str, status: str) -> dict[str, Any]:
        if status not in {"active", "disabled"}:
            raise ValueError("Status inválido.")
        with self._connect() as db:
            cursor = db.execute("UPDATE citizens SET status=?, updated_at=? WHERE id=?", (status, now(), citizen_id))
            if not cursor.rowcount:
                raise KeyError("Cidadão não encontrado.")
        return self.get_citizen(citizen_id)

    def delete_citizen(self, citizen_id: str) -> None:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM citizens WHERE id=?", (citizen_id,))
            if not cursor.rowcount:
                raise KeyError("Cidadão não encontrado.")

    def add_message(self, citizen_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        message = {"id": str(uuid4()), "citizen_id": citizen_id, "role": role, "content": content,
                   "metadata": metadata or {}, "created_at": now()}
        with self._connect() as db:
            db.execute("INSERT INTO citizen_messages VALUES (?,?,?,?,?,?)",
                       (message["id"], citizen_id, role, content, json.dumps(message["metadata"]), message["created_at"]))
        return message

    def get_messages(self, citizen_id: str, limit: int = 40) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT * FROM (SELECT * FROM citizen_messages WHERE citizen_id=?
                ORDER BY created_at DESC LIMIT ?) ORDER BY created_at ASC""", (citizen_id, limit)).fetchall()
        return [{"id": r["id"], "citizen_id": r["citizen_id"], "role": r["role"], "content": r["content"],
                 "metadata": json.loads(r["metadata_json"]), "created_at": r["created_at"]} for r in rows]

    def clear_messages(self, citizen_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM citizen_messages WHERE citizen_id=?", (citizen_id,))

    def dashboard(self) -> dict[str, Any]:
        with self._connect() as db:
            providers = db.execute("SELECT COUNT(*) FROM api_connections").fetchone()[0]
            citizens = db.execute("SELECT COUNT(*) FROM citizens").fetchone()[0]
            active = db.execute("SELECT COUNT(*) FROM citizens WHERE status='active'").fetchone()[0]
            messages = db.execute("SELECT COUNT(*) FROM citizen_messages").fetchone()[0]
        return {"nation": "Lunz", "government": "Governo de Lunz", "system": "LUNZ SOVEREIGN / ACIA",
                "api_connections": providers, "citizens": citizens, "active_citizens": active, "messages": messages}

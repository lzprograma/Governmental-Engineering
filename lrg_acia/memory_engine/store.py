"""Memória persistente SQLite com proveniência, retenção e trilha de eventos."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL,
                valid_until TEXT,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                producer TEXT NOT NULL,
                event_type TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                sensitivity TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS relations (
                relation_id TEXT PRIMARY KEY,
                source_entity TEXT NOT NULL,
                target_entity TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                context TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence_json TEXT NOT NULL,
                status TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_until TEXT,
                reviewer_id TEXT,
                reviewed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_relations_context ON relations(context);
            """)
            # Migração aditiva para bancos criados por versões anteriores do protótipo.
            relation_columns = {row[1] for row in conn.execute("PRAGMA table_info(relations)").fetchall()}
            if "reviewer_id" not in relation_columns:
                conn.execute("ALTER TABLE relations ADD COLUMN reviewer_id TEXT")
            if "reviewed_at" not in relation_columns:
                conn.execute("ALTER TABLE relations ADD COLUMN reviewed_at TEXT")

    def add_memory(self, memory_id: str, memory_type: str, content: str, source: str,
                   confidence: float, metadata: dict[str, Any] | None = None,
                   ttl_days: int | None = None) -> None:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence deve estar entre 0 e 1")
        created = datetime.now(timezone.utc)
        valid_until = (created + timedelta(days=ttl_days)).isoformat() if ttl_days else None
        with self._connect() as conn:
            conn.execute("""INSERT OR REPLACE INTO memories
                (memory_id,memory_type,content,source,confidence,created_at,valid_until,metadata_json)
                VALUES (?,?,?,?,?,?,?,?)""",
                (memory_id, memory_type, content, source, confidence, created.isoformat(),
                 valid_until, json.dumps(metadata or {}, ensure_ascii=False)))

    def search_memories(self, query: str, memory_type: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if limit < 1 or limit > 500:
            raise ValueError("limit deve estar entre 1 e 500")
        like = f"%{query}%"
        sql = "SELECT * FROM memories WHERE (content LIKE ? OR source LIKE ?)"
        params: list[Any] = [like, like]
        if memory_type:
            sql += " AND memory_type=?"
            params.append(memory_type)
        sql += " AND (valid_until IS NULL OR valid_until > ?) ORDER BY created_at DESC LIMIT ?"
        params.extend([datetime.now(timezone.utc).isoformat(), limit])
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata_json"])} for row in rows]

    def record_event(self, event: Any) -> None:
        payload = dict(event.payload)
        with self._connect() as conn:
            conn.execute("""INSERT INTO audit_events
                (event_id,timestamp,producer,event_type,trace_id,payload_json,sensitivity)
                VALUES (?,?,?,?,?,?,?)""",
                (event.event_id, event.timestamp, event.producer, event.event_type,
                 event.trace_id, json.dumps(payload, ensure_ascii=False, default=str), event.sensitivity))

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def add_relation(self, relation: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute("""INSERT OR REPLACE INTO relations
                (relation_id,source_entity,target_entity,relation_type,context,confidence,
                 evidence_json,status,valid_from,valid_until)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (relation["relation_id"], relation["source"], relation["target"],
                 relation["relation_type"], relation.get("context", "default"),
                 relation["confidence"], json.dumps(relation.get("evidence", []), ensure_ascii=False),
                 relation.get("status", "candidate"), relation.get("valid_from", datetime.now(timezone.utc).isoformat()),
                 relation.get("valid_until")))

    def get_relations(self, context: str = "default", include_candidates: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM relations WHERE context=?"
        params: list[Any] = [context]
        if not include_candidates:
            sql += " AND status='verified'"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [{**dict(row), "evidence": json.loads(row["evidence_json"])} for row in rows]

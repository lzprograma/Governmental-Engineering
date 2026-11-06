"""Motor RAGI: relações tipadas, proveniência, validade e composição restrita."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Iterable
from ..memory_engine.store import MemoryStore


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    relation_type: str
    evidence: tuple[str, ...]
    confidence: float
    context: str = "default"
    status: str = "candidate"
    valid_from: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    valid_until: str | None = None
    relation_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.source or not self.target or not self.relation_type:
            raise ValueError("source, target e relation_type são obrigatórios")
        if not self.evidence:
            raise ValueError("Uma relação RAGI exige ao menos uma referência de evidência.")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence deve estar entre 0 e 1")


class RAGIEngine:
    """A inferência transitiva só ocorre para tipos declarados explicitamente."""
    def __init__(self, store: MemoryStore, transitive_types: Iterable[str] = (),
                 incompatible_pairs: Iterable[tuple[str, str]] = ()) -> None:
        self.store = store
        self.transitive_types = frozenset(transitive_types)
        self.incompatible_pairs = {frozenset(pair) for pair in incompatible_pairs}

    def propose(self, relation: Relation) -> Relation:
        self.store.add_relation({
            "relation_id": relation.relation_id, "source": relation.source,
            "target": relation.target, "relation_type": relation.relation_type,
            "context": relation.context, "confidence": relation.confidence,
            "evidence": list(relation.evidence), "status": "candidate",
            "valid_from": relation.valid_from, "valid_until": relation.valid_until,
        })
        return relation

    def verify(self, relation_id: str, reviewer_id: str) -> None:
        if not reviewer_id.strip():
            raise ValueError("A verificação exige identidade de revisor.")
        with self.store._connect() as conn:
            from datetime import datetime, timezone
            cursor = conn.execute("UPDATE relations SET status='verified', reviewer_id=?, reviewed_at=? WHERE relation_id=? AND status='candidate'",
                                  (reviewer_id, datetime.now(timezone.utc).isoformat(), relation_id))
            if cursor.rowcount != 1:
                raise ValueError("Relação candidata não encontrada ou já revisada.")

    def query(self, entity: str, context: str = "default") -> list[dict]:
        relations = self.store.get_relations(context=context)
        return [r for r in relations if r["source_entity"] == entity or r["target_entity"] == entity]

    def contradictions(self, context: str = "default") -> list[tuple[dict, dict]]:
        relations = self.store.get_relations(context=context)
        conflicts: list[tuple[dict, dict]] = []
        for i, left in enumerate(relations):
            for right in relations[i + 1:]:
                same_fact = (left["source_entity"], left["target_entity"]) == (right["source_entity"], right["target_entity"])
                incompatible = frozenset((left["relation_type"], right["relation_type"])) in self.incompatible_pairs
                if same_fact and incompatible:
                    conflicts.append((left, right))
        return conflicts

    def infer_transitive(self, context: str = "default") -> list[Relation]:
        verified = self.store.get_relations(context=context)
        by_type: dict[str, list[dict]] = {}
        for item in verified:
            by_type.setdefault(item["relation_type"], []).append(item)
        inferred: list[Relation] = []
        existing_all = self.store.get_relations(context=context, include_candidates=True)
        existing_keys = {(r["source_entity"], r["target_entity"], r["relation_type"]) for r in existing_all}
        for relation_type, edges in by_type.items():
            if relation_type not in self.transitive_types:
                continue
            for left in edges:
                for right in edges:
                    if left["target_entity"] != right["source_entity"]:
                        continue
                    if left["source_entity"] == right["target_entity"]:
                        continue
                    evidence = tuple(dict.fromkeys(left["evidence"] + right["evidence"]))
                    # Agregação conservadora: não assume independência das fontes.
                    confidence = min(float(left["confidence"]), float(right["confidence"]))
                    key = (left["source_entity"], right["target_entity"], relation_type)
                    if key in existing_keys:
                        continue
                    candidate = Relation(left["source_entity"], right["target_entity"], relation_type,
                                         evidence, confidence, context=context, status="candidate")
                    self.propose(candidate)
                    inferred.append(candidate)
                    existing_keys.add(key)
        return inferred

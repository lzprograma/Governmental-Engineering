from __future__ import annotations
from typing import Any
from uuid import uuid4
from .contracts import Event


def make_event(producer: str, event_type: str, payload: dict[str, Any], *,
               trace_id: str | None = None, sensitivity: str = "public",
               policy_tags: tuple[str, ...] = ()) -> Event:
    return Event(producer=producer, event_type=event_type, payload=payload,
                 trace_id=trace_id or str(uuid4()), sensitivity=sensitivity,
                 policy_tags=policy_tags)

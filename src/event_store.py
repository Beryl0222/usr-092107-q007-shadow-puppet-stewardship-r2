"""事件存储：只追加、不改写。

规则：
- 每条事件先过契约校验；
- event_id 全局唯一；
- 同一聚合的 version 必须从 1 起严格 +1；
- 同一聚合事件的 occurred_at 不得早于上一条（更正只能追加后继记录）；
- 公开扫码事件在写入时即做脱敏检查，防止内部信息进入公开视图；
- 事件一经接收不可修改、不可删除（修复前后照片随 REPAIR_DOCUMENTED 永久保留）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.contracts import ContractError, validate_event, validate_public_payload


class EventStore:
    def __init__(self) -> None:
        self._events: list[dict] = []
        self._ids: set[str] = set()
        self._versions: dict[str, int] = {}
        self._last_at: dict[str, str] = {}

    @property
    def events(self) -> tuple[dict, ...]:
        return tuple(self._events)

    def append(self, event: dict) -> dict:
        errors = validate_event(event)
        if errors:
            raise ContractError("；".join(errors))

        event_id = event["event_id"]
        aggregate_id = event["aggregate_id"]
        version = event["version"]

        if event_id in self._ids:
            raise ContractError(f"event_id 已存在：{event_id}")
        expected = self._versions.get(aggregate_id, 0) + 1
        if version != expected:
            raise ContractError(
                f"聚合 {aggregate_id} 的下一条版本应为 {expected}，收到 {version}；"
                "已接收记录不得改写，更正请追加后继事件"
            )
        last_at = self._last_at.get(aggregate_id)
        if last_at is not None and event["occurred_at"] < last_at:
            raise ContractError(
                f"聚合 {aggregate_id} 新事件时间早于既有记录（{last_at}）；"
                "补记请使用不早于该时间的更正事件"
            )

        if event["event_type"] == "PUBLIC_PROFILE_PUBLISHED":
            violations = validate_public_payload(event.get("payload", {}))
            if violations:
                raise ContractError("公开资料脱敏未通过：" + "；".join(violations))

        self._events.append(event)
        self._ids.add(event_id)
        self._versions[aggregate_id] = version
        self._last_at[aggregate_id] = event["occurred_at"]
        return event

    def append_many(self, events: list[dict]) -> None:
        for event in events:
            self.append(event)

    def for_aggregate(self, aggregate_id: str) -> tuple[dict, ...]:
        return tuple(e for e in self._events if e["aggregate_id"] == aggregate_id)

    def by_type(self, event_type: str) -> tuple[dict, ...]:
        return tuple(e for e in self._events if e["event_type"] == event_type)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in self._events) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "EventStore":
        store = cls()
        text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
        for line in text.splitlines():
            line = line.strip()
            if line:
                store.append(json.loads(line))
        return store

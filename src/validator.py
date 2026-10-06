"""校验领域事件信封与核心业务规则。

两层校验：
- validate_event(record)：单条事件的信封与载荷形状，不依赖其他事件。
- validate_log(events)：事件流级别的不变量，包括老物件用途限制、
  最低阵容可行性、出入库闭环、版本递增。

修缮前后照片只增不删：事件类型中不存在删除照片的事件，
REPAIR_DOCUMENTED 必须同时携带修缮前后照片引用。
"""

from __future__ import annotations

from datetime import datetime

REQUIRED = ("event_id", "event_type", "aggregate_type", "aggregate_id", "occurred_at", "version", "summary")

EVENT_TYPES = {
    "OBJECT_REGISTERED",
    "OBJECT_CLASSIFIED",
    "DAMAGE_RECORDED",
    "REPAIR_DOCUMENTED",
    "SUBSTITUTE_PROP_DESIGNATED",
    "SCRIPT_VERSION_REVIEWED",
    "ROLE_QUALIFICATION_GRANTED",
    "ACCOMPANIMENT_QUALIFICATION_GRANTED",
    "ARTIST_AVAILABILITY_CHANGED",
    "INSTRUMENT_STATUS_CHANGED",
    "VENUE_CONDITIONS_CONFIRMED",
    "ROSTER_CONFIRMED",
    "TRANSPORT_MANIFEST_ISSUED",
    "OBJECT_CHECKED_OUT",
    "OBJECT_CHECKED_IN",
    "PERFORMANCE_LOGGED",
    "PUBLIC_QR_CONTENT_PUBLISHED",
}

AGGREGATE_TYPES = {
    "puppet_object",
    "repertoire_version",
    "artist",
    "instrument",
    "venue",
    "performance",
    "performance_roster",
    "loan_handoff",
    "public_qr_content",
}

USAGE_CLASSES = {"heritage_research_only", "controlled_display", "performance", "substitute_prop"}
# 老物件默认只用于研究或受控展示
HERITAGE_CLASSES = {"heritage_research_only", "controlled_display"}
HERITAGE_ALLOWED_PURPOSES = {"research", "controlled_display"}
CHECKOUT_PURPOSES = {"research", "controlled_display", "rehearsal", "performance", "external_repair"}

# 公开扫码内容中禁止出现的字段（含嵌套）
QR_FORBIDDEN_KEYS = {"storage_location", "minor_artists", "unpublished_repair_details"}


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and len(value) > 0


def _require(payload: dict, errors: list[str], *names: str) -> None:
    for name in names:
        if name not in payload:
            errors.append(f"payload 缺少字段：{name}")


def _find_forbidden_keys(node: object, forbidden: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in forbidden:
                found.add(key)
            found |= _find_forbidden_keys(value, forbidden)
    elif isinstance(node, list):
        for item in node:
            found |= _find_forbidden_keys(item, forbidden)
    return found


def _validate_payload(event_type: str, payload: object) -> list[str]:
    """单事件载荷规则；payload 缺失或类型不对时只报一个错。"""
    if not isinstance(payload, dict):
        return ["缺少 payload 或 payload 不是对象"]
    errors: list[str] = []

    if event_type == "OBJECT_REGISTERED":
        _require(payload, errors, "component", "material", "era")
    elif event_type == "OBJECT_CLASSIFIED":
        _require(payload, errors, "usage_class")
        if payload.get("usage_class") not in USAGE_CLASSES:
            errors.append("usage_class 必须是 heritage_research_only / controlled_display / performance / substitute_prop 之一")
    elif event_type == "DAMAGE_RECORDED":
        _require(payload, errors, "condition", "photo_ids")
        if not payload.get("photo_ids"):
            errors.append("病害记录必须附照片")
    elif event_type == "REPAIR_DOCUMENTED":
        _require(payload, errors, "method", "before_photo_ids", "after_photo_ids")
        if not payload.get("before_photo_ids") or not payload.get("after_photo_ids"):
            errors.append("修缮记录必须同时附修缮前后照片，且照片归档后不得删除")
    elif event_type == "SUBSTITUTE_PROP_DESIGNATED":
        _require(payload, errors, "stands_in_for")
    elif event_type == "SCRIPT_VERSION_REVIEWED":
        _require(payload, errors, "adaptation_type", "lyrics_source_review", "occasion_review", "role_ids")
        if payload.get("adaptation_type") not in ("traditional", "new_era_adaptation"):
            errors.append("adaptation_type 必须是 traditional 或 new_era_adaptation")
        for key in ("lyrics_source_review", "occasion_review"):
            review = payload.get(key)
            if isinstance(review, dict) and review.get("status") not in ("approved", "rejected"):
                errors.append(f"{key}.status 必须是 approved 或 rejected")
    elif event_type == "ROLE_QUALIFICATION_GRANTED":
        _require(payload, errors, "role_id")
    elif event_type == "ACCOMPANIMENT_QUALIFICATION_GRANTED":
        _require(payload, errors, "instrument_type")
    elif event_type == "ARTIST_AVAILABILITY_CHANGED":
        _require(payload, errors, "status")
        if payload.get("status") not in ("available", "absent", "retired"):
            errors.append("status 必须是 available / absent / retired 之一")
    elif event_type == "INSTRUMENT_STATUS_CHANGED":
        _require(payload, errors, "instrument_type", "status")
        if payload.get("status") not in ("operational", "faulty"):
            errors.append("status 必须是 operational 或 faulty")
    elif event_type == "VENUE_CONDITIONS_CONFIRMED":
        _require(payload, errors, "confirmed_by", "performance_date", "conditions")
    elif event_type == "ROSTER_CONFIRMED":
        _require(payload, errors, "performance_id", "repertoire_version_id", "minimum_cast", "entries")
        cast = payload.get("minimum_cast")
        if isinstance(cast, dict) and ("roles" not in cast or "instruments" not in cast):
            errors.append("minimum_cast 必须包含 roles 与 instruments")
        if not payload.get("entries"):
            errors.append("entries 不能为空")
    elif event_type == "TRANSPORT_MANIFEST_ISSUED":
        _require(payload, errors, "performance_id", "object_ids")
        if not payload.get("object_ids"):
            errors.append("运输清单不能为空")
    elif event_type == "OBJECT_CHECKED_OUT":
        _require(payload, errors, "object_id", "purpose", "custodian", "expected_return_at")
        if payload.get("purpose") not in CHECKOUT_PURPOSES:
            errors.append("purpose 必须是 research / controlled_display / rehearsal / performance / external_repair 之一")
    elif event_type == "OBJECT_CHECKED_IN":
        _require(payload, errors, "object_id", "returned_by", "condition_on_return")
    elif event_type == "PERFORMANCE_LOGGED":
        _require(payload, errors, "performance_id", "venue_id", "repertoire_version_ids")
    elif event_type == "PUBLIC_QR_CONTENT_PUBLISHED":
        _require(payload, errors, "story", "reviewed_by")
        leaked = _find_forbidden_keys(payload, QR_FORBIDDEN_KEYS)
        if leaked:
            errors.append(f"扫码内容不得包含：{'、'.join(sorted(leaked))}（藏品库位、未成年人资料、未公开修复细节）")
    return errors


def validate_event(record: dict) -> list[str]:
    errors = [f"缺少字段：{name}" for name in REQUIRED if name not in record]
    if "version" in record and (not isinstance(record["version"], int) or record["version"] < 1):
        errors.append("version 必须是正整数")
    if "event_type" in record and record["event_type"] not in EVENT_TYPES:
        errors.append(f"未知事件类型：{record['event_type']}")
    if "aggregate_type" in record and record["aggregate_type"] not in AGGREGATE_TYPES:
        errors.append(f"未知聚合类型：{record['aggregate_type']}")
    if "occurred_at" in record:
        try:
            datetime.fromisoformat(str(record["occurred_at"]))
        except ValueError:
            errors.append("occurred_at 必须是 ISO 8601 日期时间")
    if "event_type" in record and record.get("event_type") in EVENT_TYPES:
        errors.extend(_validate_payload(record["event_type"], record.get("payload")))
    return errors


def assess_feasibility(
    minimum_cast: dict,
    entries: list[dict],
    role_qualified: set[tuple[str, str]],
    accompaniment_qualified: set[tuple[str, str]],
    available: set[str],
    instruments_ok: dict[str, int],
) -> list[str]:
    """按节目最低阵容判断是否还能演出，返回问题列表（空列表表示可演）。

    - minimum_cast: {"roles": {role_id: 人数}, "instruments": {乐器类型: 件数}}
    - entries: 阵容名单，每人含 artist_id，可含 role_id 或 instrument_type
    - role_qualified / accompaniment_qualified: 已授予资格的 (artist_id, 目标) 对
    - available: 当前可出勤的艺人 id 集合（高龄退出、学徒缺席者不在内）
    - instruments_ok: 乐器类型到当前完好件数的映射（故障不计）
    """
    problems: list[str] = []
    present = [e for e in entries if e.get("artist_id") in available]

    for role_id, needed in minimum_cast.get("roles", {}).items():
        count = sum(
            1
            for e in present
            if e.get("role_id") == role_id and (e["artist_id"], role_id) in role_qualified
        )
        if count < needed:
            problems.append(f"角色 {role_id} 最低需要 {needed} 人，当前合格且在勤 {count} 人")

    for instrument_type, needed in minimum_cast.get("instruments", {}).items():
        players = sum(
            1
            for e in present
            if e.get("instrument_type") == instrument_type
            and (e["artist_id"], instrument_type) in accompaniment_qualified
        )
        if players < needed:
            problems.append(f"乐器 {instrument_type} 最低需要 {needed} 名伴奏，当前合格且在勤 {players} 人")
        if instruments_ok.get(instrument_type, 0) < needed:
            problems.append(f"乐器 {instrument_type} 最低需要 {needed} 件，当前完好 {instruments_ok.get(instrument_type, 0)} 件")
    return problems


def validate_log(events: list[dict]) -> list[str]:
    """事件流级别的不变量。events 按发生顺序给出。"""
    errors: list[str] = []
    versions: dict[tuple[str, str], int] = {}
    usage_class: dict[str, str] = {}
    outstanding: dict[str, str] = {}  # object_id -> checkout event_id
    role_qualified: set[tuple[str, str]] = set()
    accompaniment_qualified: set[tuple[str, str]] = set()
    available: set[str] = set()
    instrument_status: dict[str, tuple[str, str]] = {}  # instrument_id -> (instrument_type, status)

    for event in events:
        event_errors = validate_event(event)
        errors.extend(f"{event.get('event_id', '?')}：{msg}" for msg in event_errors)
        if event_errors:
            continue

        key = (event["aggregate_type"], event["aggregate_id"])
        expected = versions.get(key, 0) + 1
        if event["version"] != expected:
            errors.append(f"{event['event_id']}：版本应为 {expected}，实际为 {event['version']}（不得跳号或原地改写）")
        versions[key] = event["version"]

        etype = event["event_type"]
        payload = event["payload"]

        if etype == "OBJECT_CLASSIFIED":
            usage_class[event["aggregate_id"]] = payload["usage_class"]
        elif etype == "OBJECT_CHECKED_OUT":
            object_id = payload["object_id"]
            if usage_class.get(object_id) in HERITAGE_CLASSES and payload["purpose"] not in HERITAGE_ALLOWED_PURPOSES:
                errors.append(f"{event['event_id']}：老物件 {object_id} 仅可用于研究或受控展示，不得用于 {payload['purpose']}")
            if object_id in outstanding:
                errors.append(f"{event['event_id']}：物件 {object_id} 尚未归还不能再次出库")
            outstanding[object_id] = event["event_id"]
        elif etype == "OBJECT_CHECKED_IN":
            if payload["object_id"] not in outstanding:
                errors.append(f"{event['event_id']}：物件 {payload['object_id']} 未出库却登记归还")
            outstanding.pop(payload["object_id"], None)
        elif etype == "TRANSPORT_MANIFEST_ISSUED":
            for object_id in payload["object_ids"]:
                if usage_class.get(object_id) == "heritage_research_only":
                    errors.append(f"{event['event_id']}：仅限研究的老物件 {object_id} 不得进入运输清单")
        elif etype == "ROLE_QUALIFICATION_GRANTED":
            role_qualified.add((event["aggregate_id"], payload["role_id"]))
            available.add(event["aggregate_id"])
        elif etype == "ACCOMPANIMENT_QUALIFICATION_GRANTED":
            accompaniment_qualified.add((event["aggregate_id"], payload["instrument_type"]))
            available.add(event["aggregate_id"])
        elif etype == "ARTIST_AVAILABILITY_CHANGED":
            if payload["status"] == "available":
                available.add(event["aggregate_id"])
            else:
                available.discard(event["aggregate_id"])
        elif etype == "INSTRUMENT_STATUS_CHANGED":
            instrument_status[event["aggregate_id"]] = (payload["instrument_type"], payload["status"])
        elif etype == "ROSTER_CONFIRMED":
            instruments_ok: dict[str, int] = {}
            for instrument_type, status in instrument_status.values():
                if status == "operational":
                    instruments_ok[instrument_type] = instruments_ok.get(instrument_type, 0) + 1
            problems = assess_feasibility(
                payload["minimum_cast"],
                payload["entries"],
                role_qualified,
                accompaniment_qualified,
                available,
                instruments_ok,
            )
            errors.extend(f"{event['event_id']}：最低阵容不满足——{p}" for p in problems)

    for object_id, checkout_id in outstanding.items():
        errors.append(f"物件 {object_id} 自 {checkout_id} 出库后未闭环归还")
    return errors

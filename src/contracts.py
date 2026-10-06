"""领域事件目录与校验。

事件是唯一的事实来源：所有变化只能追加事件，标识、发生时间与版本不得原地
改写；信息更正以新的后继事件（同聚合 version +1）表达。

事件目录（aggregate_type / event_type）见文件末尾 ``EVENT_AGGREGATES``，
README“事件目录”一节给出中文说明。
"""
from __future__ import annotations

from datetime import datetime

ENVELOPE_REQUIRED = (
    "event_id",
    "event_type",
    "aggregate_type",
    "aggregate_id",
    "occurred_at",
    "version",
    "summary",
)

# 使用策略：老物件默认 research；受控展示需审批；替身道具才用于日常演出。
USE_POLICIES = ("research", "controlled_display", "performance")
MEMBER_STATUSES = ("active", "apprentice_leave", "retired", "exited")
QUALIFICATION_STATUSES = ("active", "suspended", "revoked")
INSTRUMENT_STATUSES = ("available", "faulty", "retired")
APPROVAL_DECISIONS = ("approved", "rejected")
OCCASIONS = ("countryside_tour", "school", "cultural_festival", "controlled_display", "research")

# event_type -> 允许的 aggregate_type
EVENT_AGGREGATES: dict[str, tuple[str, ...]] = {
    "OBJECT_CLASSIFIED": ("puppet_object",),
    "COMPONENT_REGISTERED": ("puppet_object",),
    "CONDITION_ASSESSED": ("puppet_object",),
    "REPAIR_DOCUMENTED": ("puppet_object",),
    "REPLICA_DESIGNATED": ("puppet_object",),
    "ROLE_DEFINED": ("role",),
    "PERSON_REGISTERED": ("person",),
    "ROLE_QUALIFICATION_GRANTED": ("person",),
    "ACCOMPANIMENT_QUALIFICATION_GRANTED": ("person",),
    "MEMBER_STATUS_CHANGED": ("person",),
    "INSTRUMENT_REGISTERED": ("instrument",),
    "INSTRUMENT_STATUS_CHANGED": ("instrument",),
    "PROGRAM_MIN_STAFF_DEFINED": ("program",),
    "SCRIPT_VERSION_CREATED": ("repertoire_version",),
    "LYRICS_APPROVED": ("repertoire_version",),
    "OCCASION_APPROVED": ("repertoire_version",),
    "VENUE_CONDITIONS_RECORDED": ("venue",),
    "ROSTER_CONFIRMED": ("performance_roster",),
    "TRIP_PLAN_ISSUED": ("trip",),
    "OBJECT_CHECKED_OUT": ("loan_handoff",),
    "OBJECT_RETURNED": ("loan_handoff",),
    "PERFORMANCE_LOGGED": ("performance_roster",),
    "PUBLIC_PROFILE_PUBLISHED": ("puppet_object", "repertoire_version", "role"),
}

EVENT_TYPES = tuple(EVENT_AGGREGATES)
AGGREGATE_TYPES = (
    "puppet_object",
    "repertoire_version",
    "performance_roster",
    "loan_handoff",
    "role",
    "person",
    "instrument",
    "program",
    "venue",
    "trip",
)

# 每种事件的载荷约定：required 为必填字段，types 给出字段类型，enums 给出取值域。
_PAYLOAD_SPECS: dict[str, dict] = {
    "OBJECT_CLASSIFIED": {
        "required": ("name", "category", "material", "era", "use_policy"),
        "types": {"name": str, "category": str, "material": str, "era": str,
                  "use_policy": str, "storage_location": str, "year_estimate": str,
                  "heritage_note": str},
        "enums": {"use_policy": USE_POLICIES},
    },
    "COMPONENT_REGISTERED": {
        "required": ("parent_object_id", "name", "position", "material", "era", "use_policy"),
        "types": {"parent_object_id": str, "name": str, "position": str, "material": str,
                  "era": str, "use_policy": str, "storage_location": str},
        "enums": {"use_policy": USE_POLICIES},
    },
    "CONDITION_ASSESSED": {
        "required": ("assessment_id", "condition", "diseases", "assessor"),
        "types": {"assessment_id": str, "condition": str, "diseases": list,
                  "assessor": str, "note": str},
    },
    "REPAIR_DOCUMENTED": {
        "required": ("repair_id", "status", "scope", "method", "repaired_by", "before_photos"),
        "types": {"repair_id": str, "status": str, "scope": str, "method": str,
                  "repaired_by": str, "before_photos": list, "after_photos": list,
                  "started_at": str, "completed_at": str, "materials_used": list,
                  "private_note": str, "disclosed": bool},
        "enums": {"status": ("in_progress", "completed")},
    },
    "REPLICA_DESIGNATED": {
        "required": ("target_object_id", "replica_type"),
        "types": {"target_object_id": str, "replica_type": str, "quality_note": str},
        "enums": {"replica_type": ("performance", "display")},
    },
    "ROLE_DEFINED": {
        "required": ("name", "role_kind"),
        "types": {"name": str, "role_kind": str, "note": str},
    },
    "PERSON_REGISTERED": {
        "required": ("name", "is_minor"),
        "types": {"name": str, "is_minor": bool, "birth_year": int, "contact": str,
                  "apprentice_of": str, "note": str},
    },
    "ROLE_QUALIFICATION_GRANTED": {
        "required": ("role_id", "status"),
        "types": {"role_id": str, "status": str, "note": str},
        "enums": {"status": QUALIFICATION_STATUSES},
    },
    "ACCOMPANIMENT_QUALIFICATION_GRANTED": {
        "required": ("instrument_id", "status"),
        "types": {"instrument_id": str, "status": str, "note": str},
        "enums": {"status": QUALIFICATION_STATUSES},
    },
    "MEMBER_STATUS_CHANGED": {
        "required": ("status", "reason"),
        "types": {"status": str, "reason": str},
        "enums": {"status": MEMBER_STATUSES},
    },
    "INSTRUMENT_REGISTERED": {
        "required": ("name", "instrument_kind"),
        "types": {"name": str, "instrument_kind": str, "transport_note": str},
    },
    "INSTRUMENT_STATUS_CHANGED": {
        "required": ("status", "reason"),
        "types": {"status": str, "reason": str, "transport_note": str},
        "enums": {"status": INSTRUMENT_STATUSES},
    },
    "PROGRAM_MIN_STAFF_DEFINED": {
        "required": ("title", "cast_requirements", "accompaniment_requirements"),
        "types": {"title": str, "cast_requirements": list,
                  "accompaniment_requirements": list, "required_object_ids": list,
                  "note": str},
    },
    "SCRIPT_VERSION_CREATED": {
        "required": ("program_id", "title", "version_label", "lineage", "lyrics_source"),
        "types": {"program_id": str, "title": str, "version_label": str, "lineage": str,
                  "lyrics_source": str, "based_on_version_id": str, "synopsis": str,
                  "public_synopsis": str},
        "enums": {"lineage": ("traditional", "new_era_adaptation")},
    },
    "LYRICS_APPROVED": {
        "required": ("lyrics_source", "decision", "approved_by"),
        "types": {"lyrics_source": str, "decision": str, "approved_by": str, "note": str},
        "enums": {"decision": APPROVAL_DECISIONS},
    },
    "OCCASION_APPROVED": {
        "required": ("occasion", "decision", "approved_by"),
        "types": {"occasion": str, "decision": str, "approved_by": str, "conditions": str},
        "enums": {"occasion": OCCASIONS, "decision": APPROVAL_DECISIONS},
    },
    "VENUE_CONDITIONS_RECORDED": {
        "required": ("name", "performance_date", "conditions"),
        "types": {"name": str, "performance_date": str, "conditions": dict,
                  "transport_access": str, "contact": str},
    },
    "ROSTER_CONFIRMED": {
        "required": ("program_id", "version_id", "venue_id", "performance_date",
                     "occasion", "venue_confirmed"),
        "types": {"program_id": str, "version_id": str, "venue_id": str,
                  "performance_date": str, "occasion": str, "venue_confirmed": bool,
                  "object_ids": list, "confirmed_by": str, "note": str},
        "enums": {"occasion": OCCASIONS},
    },
    "TRIP_PLAN_ISSUED": {
        "required": ("roster_id", "objects", "cast", "accompanists", "transport"),
        "types": {"roster_id": str, "objects": list, "cast": list,
                  "accompanists": list, "transport": list, "issued_by": str, "note": str},
    },
    "OBJECT_CHECKED_OUT": {
        "required": ("trip_id", "object_id", "handler", "expected_return_at"),
        "types": {"trip_id": str, "object_id": str, "handler": str,
                  "expected_return_at": str, "substitute_for": str},
    },
    "OBJECT_RETURNED": {
        "required": ("returned_at", "condition_on_return"),
        "types": {"returned_at": str, "condition_on_return": str, "note": str,
                  "photo_uris": list},
    },
    "PERFORMANCE_LOGGED": {
        "required": ("trip_id", "performed_at"),
        "types": {"trip_id": str, "performed_at": str, "attendance": int, "note": str},
    },
    "PUBLIC_PROFILE_PUBLISHED": {
        "required": ("profile_kind", "title", "story"),
        "types": {"profile_kind": str, "title": str, "story": str, "craft_note": str,
                  "public_photo_uris": list},
        "enums": {"profile_kind": ("object", "program", "role")},
    },
}

# 公开扫码内容禁止出现的载荷字段（库位、未成年人资料、未公开修复细节等）。
PUBLIC_FORBIDDEN_FIELDS = (
    "storage_location", "contact", "private_note", "is_minor", "birth_year",
    "diseases", "condition", "appraised_value",
)
PUBLIC_FORBIDDEN_MARKERS = ("库位", "未公开", "未成年人", "身份证", "手机号", "估价")


class ContractError(ValueError):
    """事件不符合契约。"""


def _check_photos(errors: list[str], field: str, photos: object) -> None:
    if not isinstance(photos, list):
        return
    for i, photo in enumerate(photos):
        if not isinstance(photo, dict) or not photo.get("uri") or not photo.get("caption"):
            errors.append(f"payload.{field}[{i}] 需包含 uri 与 caption")


def validate_event(record: dict) -> list[str]:
    """返回错误信息列表；空列表表示通过。

    校验信封字段、事件/聚合取值、聚合版本号与该事件的载荷约定。
    修复照片要求 uri + caption；照片“不可删除”由投影与存储层保证。
    """
    errors: list[str] = [f"缺少字段：{name}" for name in ENVELOPE_REQUIRED if name not in record]
    if errors:
        return errors

    event_type = record["event_type"]
    aggregate_type = record["aggregate_type"]
    if event_type not in EVENT_AGGREGATES:
        errors.append(f"未知 event_type：{event_type}")
    elif aggregate_type not in EVENT_AGGREGATES[event_type]:
        allowed = "、".join(EVENT_AGGREGATES[event_type])
        errors.append(f"{event_type} 的 aggregate_type 应为：{allowed}")
    if aggregate_type not in AGGREGATE_TYPES:
        errors.append(f"未知 aggregate_type：{aggregate_type}")

    if not isinstance(record["version"], int) or record["version"] < 1:
        errors.append("version 必须是正整数")
    if not isinstance(record["aggregate_id"], str) or not record["aggregate_id"]:
        errors.append("aggregate_id 必须是非空字符串")
    if not isinstance(record["event_id"], str) or not record["event_id"]:
        errors.append("event_id 必须是非空字符串")
    try:
        datetime.fromisoformat(record["occurred_at"])
    except (TypeError, ValueError):
        errors.append("occurred_at 必须是 ISO 8601 日期时间")

    payload = record.get("payload")
    spec = _PAYLOAD_SPECS.get(event_type)
    if spec is not None:
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            errors.append("payload 必须是对象")
            return errors
        for name in spec["required"]:
            if name not in payload:
                errors.append(f"payload.{name} 为必填（{event_type}）")
        for name, expected in spec["types"].items():
            if name in payload and not isinstance(payload[name], expected):
                expect = expected.__name__
                errors.append(f"payload.{name} 类型应为 {expect}")
        for name, choices in spec.get("enums", {}).items():
            if name in payload and payload[name] not in choices:
                errors.append(f"payload.{name} 取值应为：{'、'.join(choices)}")
        _check_photos(errors, "before_photos", payload.get("before_photos", []))
        _check_photos(errors, "after_photos", payload.get("after_photos", []))
    return errors


def validate_public_payload(payload: dict) -> list[str]:
    """公开扫码资料的脱敏检查，返回违规原因列表。"""
    violations: list[str] = []
    blob = " ".join(
        str(v) for v in payload.values()
        if isinstance(v, (str, int, float, bool))
    )
    for name in PUBLIC_FORBIDDEN_FIELDS:
        if name in payload:
            violations.append(f"公开资料不得含内部字段：{name}")
    for marker in PUBLIC_FORBIDDEN_MARKERS:
        if marker in blob:
            violations.append(f"公开文案疑似包含受限信息：{marker}")
    for uri in payload.get("public_photo_uris", []):
        if not isinstance(uri, str) or not uri:
            violations.append("public_photo_uris 必须是非空字符串列表")
    return violations

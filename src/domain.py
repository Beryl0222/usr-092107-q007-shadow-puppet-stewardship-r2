"""业务策略：全部为针对投影状态 AppState 的纯函数。

覆盖需求中的关键判断：
- 老物件默认只用于研究/受控展示，下乡装车自动改派表演替身；
- 高龄退出、学徒缺席、乐器故障时，按节目最低阵容判断能否演出；
- 场地方确认日期与条件后，生成真正可用的节目、人员与运输清单；
- 出库拦截、演出后逐件闭环归还；
- 公开扫码视图白名单脱敏（无库位、无未成年人资料、无未公开修复细节）。
"""
from __future__ import annotations

from src.projection import AppState

# 角色/伴奏需求条目允许写成 id 字符串（数量 1）或 {"role_id"/"instrument_id", "count"}
_DATE_FMT = "%Y-%m-%d"


def _requirement(entry: dict | str, key: str) -> tuple[str, int]:
    if isinstance(entry, str):
        return entry, 1
    return entry[key], int(entry.get("count", 1))


# ---------- 人员与乐器可用性 ----------

def eligible_performers(state: AppState, role_id: str) -> list[dict]:
    """某角色当前能上场的人：资格有效，且人员状态为 active。"""
    result = []
    for person in state.persons.values():
        if person["status"] != "active":
            continue
        if person["role_qualifications"].get(role_id) == "active":
            result.append(person)
    return sorted(result, key=lambda x: x["id"])


def eligible_instrument_players(state: AppState, instrument_id: str) -> list[dict]:
    """某乐器当前能伴奏的人：伴奏资格有效且人员在团在岗。"""
    result = []
    for person in state.persons.values():
        if person["status"] != "active":
            continue
        if person["accompaniment_qualifications"].get(instrument_id) == "active":
            result.append(person)
    return sorted(result, key=lambda x: x["id"])


def instrument_usable(state: AppState, instrument_id: str) -> bool:
    instrument = state.instruments.get(instrument_id)
    return instrument is not None and instrument["status"] == "available"


# ---------- 最低阵容 ----------

def check_min_staff(state: AppState, program_id: str) -> dict:
    """按节目最低阵容逐项核对，返回可行性与缺口（不修改状态）。"""
    program = state.programs.get(program_id)
    if program is None:
        return {"feasible": False, "blocks": [f"节目不存在：{program_id}"],
                "cast": [], "accompaniment": []}

    blocks: list[str] = []
    cast_rows = []
    for entry in program["cast_requirements"]:
        role_id, count = _requirement(entry, "role_id")
        role = state.roles.get(role_id)
        candidates = eligible_performers(state, role_id)
        shortage = max(0, count - len(candidates))
        row = {
            "role_id": role_id,
            "role_name": role["name"] if role else role_id,
            "required": count,
            "available": len(candidates),
            "assigned": [p["id"] for p in candidates[:count]],
            "shortage": shortage,
        }
        cast_rows.append(row)
        if role is None:
            blocks.append(f"角色未建档：{role_id}")
        elif shortage:
            blocks.append(f"角色「{row['role_name']}」缺 {shortage} 人（需 {count}，在岗合格 {len(candidates)}）")

    accompaniment_rows = []
    for entry in program["accompaniment_requirements"]:
        instrument_id, count = _requirement(entry, "instrument_id")
        instrument = state.instruments.get(instrument_id)
        players = eligible_instrument_players(state, instrument_id)
        usable = instrument_usable(state, instrument_id)
        # 乐器故障时，即使有人能演奏也无法满足该伴奏位
        effective = len(players) if usable else 0
        shortage = max(0, count - effective)
        row = {
            "instrument_id": instrument_id,
            "instrument_name": instrument["name"] if instrument else instrument_id,
            "required": count,
            "qualified_players": len(players),
            "instrument_status": instrument["status"] if instrument else "missing",
            "assigned": [p["id"] for p in players[:count]],
            "shortage": shortage,
        }
        accompaniment_rows.append(row)
        if instrument is None:
            blocks.append(f"乐器未建档：{instrument_id}")
        elif not usable:
            blocks.append(f"乐器「{row['instrument_name']}」状态为 {instrument['status']}，无法伴奏")
        elif shortage:
            blocks.append(
                f"伴奏「{row['instrument_name']}」缺 {shortage} 人（需 {count}，在岗合格 {len(players)}）")

    return {"feasible": not blocks, "blocks": blocks,
            "cast": cast_rows, "accompaniment": accompaniment_rows}


# ---------- 物件使用策略与替身 ----------

def object_usable_for_occasion(obj: dict, occasion: str) -> tuple[bool, str]:
    """老物件使用策略。返回 (是否可出库, 原因)。"""
    if obj is None:
        return False, "物件未建档"
    if obj.get("under_repair"):
        return False, "正在修缮中"
    policy = obj["use_policy"]
    if policy == "research":
        return False, "老物件默认仅用于研究，不得作为演出道具出库"
    if policy == "controlled_display":
        if occasion != "controlled_display":
            return False, "受控展示物件未经审批不得用于日常演出"
        return True, "受控展示批准用途"
    return True, "表演用道具"


def find_performance_replica(state: AppState, original_id: str) -> dict | None:
    """为老物件寻找可下乡的表演替身（表演用途、非修缮中）。"""
    original = state.objects.get(original_id)
    if original is None:
        return None
    for replica_id in original.get("replicas", []):
        replica = state.objects.get(replica_id)
        if (replica is not None and replica["use_policy"] == "performance"
                and replica.get("replica_type") == "performance"
                and not replica.get("under_repair")):
            return replica
    return None


def object_currently_out(state: AppState, object_id: str, exclude_handoff: str | None = None) -> dict | None:
    for handoff in state.handoffs.values():
        if handoff["object_id"] == object_id and handoff["returned_at"] is None:
            if exclude_handoff and handoff["id"] == exclude_handoff:
                continue
            return handoff
    return None


# ---------- 版本审定 ----------

def version_stage_ready(version: dict, occasion: str) -> tuple[bool, list[str]]:
    """唱词来源与适用场合须分别审定通过。"""
    blocks = []
    approval = version.get("lyrics_approval")
    if approval is None or approval["decision"] != "approved":
        blocks.append(f"唱词来源「{version['lyrics_source']}」尚未审定通过")
    occasion_approval = version.get("occasion_approvals", {}).get(occasion)
    if occasion_approval is None or occasion_approval["decision"] != "approved":
        blocks.append(f"版本 {version['version_label']} 未取得 {occasion} 场合审定")
    return not blocks, blocks


# ---------- 场地方确认后的可用节目与下乡清单 ----------

def feasible_programs_for_venue(state: AppState, venue_id: str, occasion: str) -> list[dict]:
    """场地已确认日期和条件后，列出“真正能演”的节目：
    有通过唱词与场合审定的版本、最低阵容当前可满足。"""
    venue = state.venues.get(venue_id)
    if venue is None:
        return []
    picks = []
    for version in state.versions.values():
        ok, _ = version_stage_ready(version, occasion)
        if not ok:
            continue
        staff = check_min_staff(state, version["program_id"])
        if not staff["feasible"]:
            continue
        program = state.programs[version["program_id"]]
        picks.append({
            "program_id": program["id"], "title": program["title"],
            "version_id": version["id"], "version_label": version["version_label"],
            "lineage": version["lineage"],
        })
    return sorted(picks, key=lambda x: (x["title"], x["version_label"]))


def _resolve_load_list(state: AppState, roster: dict) -> tuple[list[dict], list[str]]:
    """把排班申请的物件解析为实际装车清单：老物件自动改派替身。"""
    occasion = roster["occasion"]
    items, warnings = [], []
    for object_id in roster["object_ids"]:
        obj = state.objects.get(object_id)
        usable, reason = object_usable_for_occasion(obj, occasion)
        if usable:
            items.append({"requested_id": object_id, "load_id": object_id,
                          "name": obj["name"], "status": "loaded", "reason": reason})
            continue
        replica = find_performance_replica(state, object_id)
        if replica is not None:
            warnings.append(
                f"「{obj['name'] if obj else object_id}」不可装车（{reason}），"
                f"改派表演替身「{replica['name']}」（{replica['id']}）")
            items.append({"requested_id": object_id, "load_id": replica["id"],
                          "name": replica["name"], "status": "replaced",
                          "reason": reason, "replica_for": object_id})
        else:
            warnings.append(
                f"「{obj['name'] if obj else object_id}」不可装车（{reason}），且无表演替身")
            items.append({"requested_id": object_id, "load_id": None,
                          "name": obj["name"] if obj else object_id,
                          "status": "blocked", "reason": reason})
    return items, warnings


def _transport_checklist(state: AppState, staff: dict, load_items: list[dict],
                         venue: dict) -> list[dict]:
    checklist = [{"item": "影窗、灯源与挂架", "requirement": "按场地条件核对电源与台口尺寸"}]
    conditions = venue.get("conditions", {})
    if conditions:
        checklist.append({"item": f"场地：{venue['name']}",
                          "requirement": "；".join(f"{k}={v}" for k, v in conditions.items())})
    if venue.get("transport_access"):
        checklist.append({"item": "进场通道", "requirement": venue["transport_access"]})
    for row in staff["accompaniment"]:
        instrument = state.instruments.get(row["instrument_id"])
        if instrument and instrument.get("transport_note"):
            checklist.append({"item": instrument["name"],
                              "requirement": instrument["transport_note"]})
    for item in load_items:
        if item["status"] == "replaced":
            checklist.append({"item": item["name"], "requirement": "表演替身，常规道具囊匣"})
    return checklist


def build_trip_plan(state: AppState, roster_id: str) -> dict:
    """场地确认后生成真正可用的节目、人员与运输清单。"""
    roster = state.rosters.get(roster_id)
    if roster is None:
        return {"feasible": False, "roster_id": roster_id,
                "blocks": [f"排班不存在：{roster_id}"]}

    blocks: list[str] = []
    if not roster["venue_confirmed"]:
        blocks.append("场地方尚未确认日期与条件")

    version = state.versions.get(roster["version_id"])
    program = state.programs.get(roster["program_id"])
    venue = state.venues.get(roster["venue_id"])
    if program is None:
        blocks.append("节目未建档")
    if version is None:
        blocks.append("剧目版本未建档")
    else:
        ok, stage_blocks = version_stage_ready(version, roster["occasion"])
        blocks.extend(stage_blocks)
    if venue is None:
        blocks.append("场地未建档")

    staff = check_min_staff(state, roster["program_id"]) if program else {
        "feasible": False, "blocks": [], "cast": [], "accompaniment": []}
    blocks.extend(staff["blocks"])

    load_items, load_warnings = (
        _resolve_load_list(state, roster) if roster["object_ids"] else ([], []))
    if any(item["status"] == "blocked" for item in load_items):
        blocked = "、".join(i["name"] for i in load_items if i["status"] == "blocked")
        blocks.append(f"以下物件无法装车且无替身：{blocked}")

    transport = _transport_checklist(state, staff, load_items, venue) if venue else []

    return {
        "feasible": not blocks,
        "roster_id": roster_id,
        "occasion": roster["occasion"],
        "performance_date": roster["performance_date"],
        "program": {"id": program["id"], "title": program["title"]} if program else None,
        "version": ({"id": version["id"], "version_label": version["version_label"],
                     "lineage": version["lineage"]} if version else None),
        "venue": {"id": venue["id"], "name": venue["name"]} if venue else None,
        "blocks": blocks,
        "warnings": load_warnings,
        "cast": staff["cast"],
        "accompaniment": staff["accompaniment"],
        "objects": load_items,
        "transport": transport,
    }


# ---------- 出库交接 ----------

def checkout_violations(state: AppState, payload: dict) -> list[str]:
    """OBJECT_CHECKED_OUT 写入前的业务校验。"""
    violations: list[str] = []
    trip = state.trips.get(payload["trip_id"])
    obj = state.objects.get(payload["object_id"])
    if trip is None:
        violations.append(f"出行计划不存在：{payload['trip_id']}")
    if obj is None:
        violations.append(f"物件未建档：{payload['object_id']}")
        return violations
    if obj.get("under_repair"):
        violations.append(f"「{obj['name']}」正在修缮，不能出库")
    open_handoff = object_currently_out(state, obj["id"])
    if open_handoff is not None:
        violations.append(f"「{obj['name']}」尚未归还（交接 {open_handoff['id']}）")
    if trip is not None:
        roster = state.rosters.get(trip["roster_id"])
        if roster is not None:
            usable, reason = object_usable_for_occasion(obj, roster["occasion"])
            if not usable:
                violations.append(f"「{obj['name']}」：{reason}")
    return violations


# ---------- 归还闭环 ----------

def return_closure(state: AppState, trip_id: str, now: str | None = None) -> dict:
    """核对一次出行的每件物品是否闭环归还。"""
    trip = state.trips.get(trip_id)
    if trip is None:
        return {"trip_id": trip_id, "all_closed": False,
                "blocks": [f"出行计划不存在：{trip_id}"], "items": []}
    handoffs = [h for h in state.handoffs.values() if h["trip_id"] == trip_id]
    by_object: dict[str, list[dict]] = {}
    for h in handoffs:
        by_object.setdefault(h["object_id"], []).append(h)

    items = []
    for planned in trip["objects"]:
        object_id = planned.get("load_id") if isinstance(planned, dict) else planned
        records = by_object.get(object_id, [])
        open_record = next((h for h in records if h["returned_at"] is None), None)
        returned = next((h for h in records if h["returned_at"] is not None), None)
        if returned is not None:
            status = "returned"
        elif open_record is not None:
            status = "outstanding"
        else:
            status = "never_checked_out"
        item = {"object_id": object_id, "status": status,
                "handoff_id": (returned or open_record or {}).get("id"),
                "checked_out_at": (open_record or returned or {}).get("checked_out_at"),
                "returned_at": returned["returned_at"] if returned else None,
                "condition_on_return": returned["condition_on_return"] if returned else None}
        if status == "outstanding" and now and open_record.get("expected_return_at"):
            item["overdue"] = now > open_record["expected_return_at"]
        items.append(item)

    all_closed = all(i["status"] == "returned" for i in items) and len(items) > 0
    return {"trip_id": trip_id, "roster_id": trip["roster_id"],
            "all_closed": all_closed, "items": items}


# ---------- 公开扫码视图（白名单脱敏） ----------

OBJECT_PUBLIC_KEYS = ("id", "name", "category", "material", "era", "year_estimate",
                      "object_kind", "replica_of")
VERSION_PUBLIC_KEYS = ("id", "program_id", "title", "version_label", "lineage",
                       "public_synopsis")
ROLE_PUBLIC_KEYS = ("id", "name", "role_kind", "note")

_PUBLIC_BUCKETS = {
    "puppet_object": (OBJECT_PUBLIC_KEYS, "object"),
    "repertoire_version": (VERSION_PUBLIC_KEYS, "program"),
    "role": (ROLE_PUBLIC_KEYS, "role"),
}


def public_card(state: AppState, aggregate_type: str, aggregate_id: str) -> dict | None:
    """生成扫码可见的介绍卡：只有技艺故事，不含库位、未成年人与未公开修缮细节。

    人员档案不提供公开卡（未成年人资料零暴露）；修缮信息只展示已公开
    （disclosed=True）的工艺性描述，照片仅限发布时列入 public_photo_uris 的内容。
    """
    if aggregate_type not in _PUBLIC_BUCKETS:
        return None
    entity = state.get(aggregate_type, aggregate_id)
    if entity is None:
        return None
    keys, kind = _PUBLIC_BUCKETS[aggregate_type]
    card = {"kind": kind, **{k: entity.get(k) for k in keys if entity.get(k) is not None}}

    if aggregate_type == "puppet_object":
        disclosed_repairs = [{
            "scope": r["scope"], "method": r["method"],
            "repaired_by": r["repaired_by"],
            "completed_at": r["completed_at"],
        } for r in entity.get("repairs", []) if r.get("disclosed") and r["status"] == "completed"]
        if disclosed_repairs:
            card["conservation_craft"] = disclosed_repairs
        if entity.get("heritage_note"):
            card["heritage_note"] = entity["heritage_note"]

    stories = [
        {"title": p["title"], "story": p["story"], "craft_note": p["craft_note"],
         "photos": p["public_photo_uris"], "published_at": p["published_at"]}
        for p in state.public_profiles
        if p["aggregate_type"] == aggregate_type and p["aggregate_id"] == aggregate_id
    ]
    card["stories"] = stories
    return card

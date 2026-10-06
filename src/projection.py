"""状态投影：把只追加的事件流还原为当前可用状态。

投影不做任何删除：
- 修缮记录中的 before_photos / after_photos 只会累积；
- 资格与人员状态的历史（退出、停演、故障）全部保留，当前值随事件演进；
- 出入库按 loan_handoff 聚合串联，归还事件只补全同一条交接记录。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppState:
    objects: dict[str, dict] = field(default_factory=dict)
    roles: dict[str, dict] = field(default_factory=dict)
    persons: dict[str, dict] = field(default_factory=dict)
    instruments: dict[str, dict] = field(default_factory=dict)
    programs: dict[str, dict] = field(default_factory=dict)
    versions: dict[str, dict] = field(default_factory=dict)
    venues: dict[str, dict] = field(default_factory=dict)
    rosters: dict[str, dict] = field(default_factory=dict)
    trips: dict[str, dict] = field(default_factory=dict)
    handoffs: dict[str, dict] = field(default_factory=dict)
    public_profiles: list[dict] = field(default_factory=list)

    def get(self, aggregate_type: str, aggregate_id: str) -> dict | None:
        bucket = {
            "puppet_object": self.objects,
            "role": self.roles,
            "person": self.persons,
            "instrument": self.instruments,
            "program": self.programs,
            "repertoire_version": self.versions,
            "venue": self.venues,
            "performance_roster": self.rosters,
            "trip": self.trips,
            "loan_handoff": self.handoffs,
        }.get(aggregate_type)
        return bucket.get(aggregate_id) if bucket is not None else None


def _extend_photos(existing: list[dict], incoming: list[dict]) -> list[dict]:
    seen = {p["uri"] for p in existing}
    merged = list(existing)
    for photo in incoming:
        if photo["uri"] not in seen:
            merged.append(photo)
            seen.add(photo["uri"])
    return merged


def build_state(events: list[dict] | tuple[dict, ...]) -> AppState:
    state = AppState()

    for event in events:
        et = event["event_type"]
        agg_id = event["aggregate_id"]
        at = event["occurred_at"]
        p = event.get("payload", {})

        if et == "OBJECT_CLASSIFIED":
            state.objects[agg_id] = {
                "id": agg_id, "name": p["name"], "category": p["category"],
                "material": p["material"], "era": p["era"],
                "year_estimate": p.get("year_estimate"),
                "use_policy": p["use_policy"],
                "storage_location": p.get("storage_location"),
                "heritage_note": p.get("heritage_note"),
                "object_kind": "whole", "parent_object_id": None,
                "components": [], "assessments": [], "repairs": [],
                "repair_index": {}, "replica_of": None, "replicas": [],
                "current_condition": None, "under_repair": False,
                "is_component": False,
            }

        elif et == "COMPONENT_REGISTERED":
            component = {
                "id": agg_id, "name": p["name"], "position": p["position"],
                "material": p["material"], "era": p["era"],
                "use_policy": p["use_policy"],
                "storage_location": p.get("storage_location"),
                "parent_object_id": p["parent_object_id"],
                "current_condition": None, "under_repair": False,
                "assessments": [], "repairs": [], "repair_index": {},
                "is_component": True, "object_kind": "component",
            }
            state.objects[agg_id] = component
            parent = state.objects.get(p["parent_object_id"])
            if parent is not None:
                parent["components"].append(agg_id)

        elif et in ("CONDITION_ASSESSED", "REPAIR_DOCUMENTED"):
            obj = state.objects.get(agg_id)
            if obj is None:
                continue
            if et == "CONDITION_ASSESSED":
                assessment = {
                    "assessment_id": p["assessment_id"], "condition": p["condition"],
                    "diseases": list(p["diseases"]), "assessor": p["assessor"],
                    "assessed_at": at, "note": p.get("note", ""),
                }
                obj["assessments"].append(assessment)
                obj["current_condition"] = p["condition"]
            else:
                repair_id = p["repair_id"]
                if repair_id not in obj["repair_index"]:
                    record = {
                        "repair_id": repair_id, "status": p["status"],
                        "scope": p["scope"], "method": p["method"],
                        "repaired_by": p["repaired_by"],
                        "before_photos": list(p["before_photos"]),
                        "after_photos": list(p.get("after_photos", [])),
                        "started_at": p.get("started_at", at),
                        "completed_at": p.get("completed_at"),
                        "materials_used": list(p.get("materials_used", [])),
                        "disclosed": p.get("disclosed", False),
                    }
                    obj["repairs"].append(record)
                    obj["repair_index"][repair_id] = record
                else:
                    record = obj["repair_index"][repair_id]
                    # 照片只增不删：任何后继修缮事件都只能补充照片。
                    record["before_photos"] = _extend_photos(
                        record["before_photos"], p["before_photos"])
                    record["after_photos"] = _extend_photos(
                        record["after_photos"], p.get("after_photos", []))
                    if p["status"] == "completed":
                        record["status"] = "completed"
                        record["completed_at"] = p.get("completed_at", at)
                    # 后续审定可将修缮工艺转为可公开；公开的只有工艺性描述。
                    if p.get("disclosed"):
                        record["disclosed"] = True
                obj["under_repair"] = record["status"] == "in_progress"

        elif et == "REPLICA_DESIGNATED":
            replica = state.objects.get(agg_id)
            original = state.objects.get(p["target_object_id"])
            if replica is not None:
                replica["replica_of"] = p["target_object_id"]
                replica["replica_type"] = p["replica_type"]
            if original is not None and agg_id not in original["replicas"]:
                original["replicas"].append(agg_id)

        elif et == "ROLE_DEFINED":
            state.roles[agg_id] = {
                "id": agg_id, "name": p["name"], "role_kind": p["role_kind"],
                "note": p.get("note", ""),
            }

        elif et == "PERSON_REGISTERED":
            state.persons[agg_id] = {
                "id": agg_id, "name": p["name"], "is_minor": p["is_minor"],
                "birth_year": p.get("birth_year"), "contact": p.get("contact"),
                "apprentice_of": p.get("apprentice_of"), "note": p.get("note"),
                "status": "active", "status_history": [],
                "role_qualifications": {}, "accompaniment_qualifications": {},
            }

        elif et == "ROLE_QUALIFICATION_GRANTED":
            person = state.persons.get(agg_id)
            if person is not None:
                person["role_qualifications"][p["role_id"]] = p["status"]

        elif et == "ACCOMPANIMENT_QUALIFICATION_GRANTED":
            person = state.persons.get(agg_id)
            if person is not None:
                person["accompaniment_qualifications"][p["instrument_id"]] = p["status"]

        elif et == "MEMBER_STATUS_CHANGED":
            person = state.persons.get(agg_id)
            if person is not None:
                person["status"] = p["status"]
                person["status_history"].append(
                    {"status": p["status"], "reason": p["reason"], "at": at})

        elif et == "INSTRUMENT_REGISTERED":
            state.instruments[agg_id] = {
                "id": agg_id, "name": p["name"], "instrument_kind": p["instrument_kind"],
                "transport_note": p.get("transport_note", ""),
                "status": "available", "status_history": [],
            }

        elif et == "INSTRUMENT_STATUS_CHANGED":
            instrument = state.instruments.get(agg_id)
            if instrument is not None:
                instrument["status"] = p["status"]
                instrument["status_history"].append(
                    {"status": p["status"], "reason": p["reason"], "at": at})
                if p.get("transport_note"):
                    instrument["transport_note"] = p["transport_note"]

        elif et == "PROGRAM_MIN_STAFF_DEFINED":
            state.programs[agg_id] = {
                "id": agg_id, "title": p["title"],
                "cast_requirements": list(p["cast_requirements"]),
                "accompaniment_requirements": list(p["accompaniment_requirements"]),
                "required_object_ids": list(p.get("required_object_ids", [])),
                "note": p.get("note", ""),
            }

        elif et == "SCRIPT_VERSION_CREATED":
            state.versions[agg_id] = {
                "id": agg_id, "program_id": p["program_id"], "title": p["title"],
                "version_label": p["version_label"], "lineage": p["lineage"],
                "lyrics_source": p["lyrics_source"],
                "based_on_version_id": p.get("based_on_version_id"),
                "synopsis": p.get("synopsis", ""),
                "public_synopsis": p.get("public_synopsis", ""),
                "lyrics_approval": None, "occasion_approvals": {},
            }

        elif et == "LYRICS_APPROVED":
            version = state.versions.get(agg_id)
            if version is not None:
                version["lyrics_approval"] = {
                    "lyrics_source": p["lyrics_source"], "decision": p["decision"],
                    "approved_by": p["approved_by"], "at": at, "note": p.get("note", ""),
                }

        elif et == "OCCASION_APPROVED":
            version = state.versions.get(agg_id)
            if version is not None:
                version["occasion_approvals"][p["occasion"]] = {
                    "decision": p["decision"], "approved_by": p["approved_by"],
                    "at": at, "conditions": p.get("conditions", ""),
                }

        elif et == "VENUE_CONDITIONS_RECORDED":
            state.venues[agg_id] = {
                "id": agg_id, "name": p["name"],
                "performance_date": p["performance_date"],
                "conditions": dict(p["conditions"]),
                "transport_access": p.get("transport_access", ""),
                "contact": p.get("contact"),
            }

        elif et == "ROSTER_CONFIRMED":
            state.rosters[agg_id] = {
                "id": agg_id, "program_id": p["program_id"],
                "version_id": p["version_id"], "venue_id": p["venue_id"],
                "performance_date": p["performance_date"], "occasion": p["occasion"],
                "venue_confirmed": p["venue_confirmed"],
                "object_ids": list(p.get("object_ids", [])),
                "confirmed_by": p.get("confirmed_by", ""), "note": p.get("note", ""),
                "confirmed_at": at, "performances": [],
            }

        elif et == "TRIP_PLAN_ISSUED":
            state.trips[agg_id] = {
                "id": agg_id, "roster_id": p["roster_id"],
                "objects": list(p["objects"]), "cast": list(p["cast"]),
                "accompanists": list(p["accompanists"]),
                "transport": list(p["transport"]),
                "issued_by": p.get("issued_by", ""), "note": p.get("note", ""),
                "issued_at": at,
            }

        elif et == "OBJECT_CHECKED_OUT":
            state.handoffs[agg_id] = {
                "id": agg_id, "trip_id": p["trip_id"], "object_id": p["object_id"],
                "handler": p["handler"], "checked_out_at": at,
                "expected_return_at": p.get("expected_return_at"),
                "substitute_for": p.get("substitute_for"),
                "returned_at": None, "condition_on_return": None,
                "return_note": None, "return_photos": [],
            }

        elif et == "OBJECT_RETURNED":
            handoff = state.handoffs.get(agg_id)
            if handoff is not None:
                handoff["returned_at"] = p["returned_at"]
                handoff["condition_on_return"] = p["condition_on_return"]
                handoff["return_note"] = p.get("note")
                handoff["return_photos"] = list(p.get("photo_uris", []))

        elif et == "PERFORMANCE_LOGGED":
            roster = state.rosters.get(agg_id)
            if roster is not None:
                roster["performances"].append({
                    "trip_id": p["trip_id"], "performed_at": p["performed_at"],
                    "attendance": p.get("attendance"), "note": p.get("note", ""),
                })

        elif et == "PUBLIC_PROFILE_PUBLISHED":
            state.public_profiles.append({
                "aggregate_type": event["aggregate_type"],
                "aggregate_id": agg_id, "profile_kind": p["profile_kind"],
                "title": p["title"], "story": p["story"],
                "craft_note": p.get("craft_note", ""),
                "public_photo_uris": list(p.get("public_photo_uris", [])),
                "published_at": at,
            })

    return state

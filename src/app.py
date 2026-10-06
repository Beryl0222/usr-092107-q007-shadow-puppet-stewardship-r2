"""应用服务：把业务操作翻译为只追加的领域事件。

所有命令都通过 EventStore.append 落库，业务规则（最低阵容、老物件拦截、
归还闭环、公开脱敏）在写入前由 src.domain 把关。
"""
from __future__ import annotations

from datetime import datetime

from src.contracts import ContractError
from src.domain import (
    build_trip_plan, checkout_violations, feasible_programs_for_venue,
    public_card, return_closure,
)
from src.event_store import EventStore
from src.projection import AppState, build_state


class DomainRuleError(ValueError):
    """业务规则不允许该操作。"""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


class TroupeSystem:
    def __init__(self, store: EventStore | None = None) -> None:
        self.store = store or EventStore()

    # ---- 基础落库 ----

    def _emit(self, event_type: str, aggregate_type: str, aggregate_id: str,
              payload: dict, *, occurred_at: str | None = None,
              version: int | None = None, summary: str = "") -> dict:
        next_version = version or self.store._versions.get(aggregate_id, 0) + 1
        event = {
            "event_id": f"{aggregate_id}#v{next_version}",
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "occurred_at": occurred_at or _now(),
            "version": next_version,
            "summary": summary or event_type,
            "payload": payload,
        }
        return self.store.append(event)

    @property
    def state(self) -> AppState:
        return build_state(self.store.events)

    # ---- 藏品：物件、部件、病害、修缮、替身 ----

    def classify_object(self, object_id: str, *, name: str, category: str, material: str,
                        era: str, use_policy: str, occurred_at: str | None = None,
                        storage_location: str | None = None, year_estimate: str | None = None,
                        heritage_note: str | None = None, summary: str = "") -> dict:
        payload = {"name": name, "category": category, "material": material, "era": era,
                   "use_policy": use_policy}
        for key, value in (("year_estimate", year_estimate),
                           ("storage_location", storage_location),
                           ("heritage_note", heritage_note)):
            if value is not None:
                payload[key] = value
        return self._emit("OBJECT_CLASSIFIED", "puppet_object", object_id, payload,
                          occurred_at=occurred_at, summary=summary or f"建档：{name}")

    def register_component(self, component_id: str, *, parent_object_id: str, name: str,
                           position: str, material: str, era: str, use_policy: str,
                           occurred_at: str | None = None,
                           storage_location: str | None = None) -> dict:
        payload = {"parent_object_id": parent_object_id, "name": name, "position": position,
                   "material": material, "era": era, "use_policy": use_policy}
        if storage_location is not None:
            payload["storage_location"] = storage_location
        return self._emit("COMPONENT_REGISTERED", "puppet_object", component_id, payload,
                          occurred_at=occurred_at, summary=f"登记部件：{name}")

    def assess_condition(self, object_id: str, *, assessment_id: str, condition: str,
                         diseases: list[str], assessor: str, occurred_at: str,
                         note: str | None = None) -> dict:
        payload = {"assessment_id": assessment_id, "condition": condition,
                   "diseases": diseases, "assessor": assessor}
        if note:
            payload["note"] = note
        return self._emit("CONDITION_ASSESSED", "puppet_object", object_id, payload,
                          occurred_at=occurred_at, summary=f"病害评估：{condition}")

    def document_repair(self, object_id: str, *, repair_id: str, status: str, scope: str,
                        method: str, repaired_by: str, before_photos: list[dict],
                        occurred_at: str, after_photos: list[dict] | None = None,
                        started_at: str | None = None, completed_at: str | None = None,
                        materials_used: list[str] | None = None, disclosed: bool = False,
                        private_note: str | None = None) -> dict:
        payload = {"repair_id": repair_id, "status": status, "scope": scope,
                   "method": method, "repaired_by": repaired_by,
                   "before_photos": before_photos, "after_photos": after_photos or [],
                   "materials_used": materials_used or [], "disclosed": disclosed}
        if started_at:
            payload["started_at"] = started_at
        if completed_at:
            payload["completed_at"] = completed_at
        if private_note:
            payload["private_note"] = private_note
        return self._emit("REPAIR_DOCUMENTED", "puppet_object", object_id, payload,
                          occurred_at=occurred_at,
                          summary=f"修缮记录：{scope}（{status}）")

    def designate_replica(self, replica_id: str, *, target_object_id: str,
                          replica_type: str, quality_note: str | None = None,
                          occurred_at: str | None = None) -> dict:
        payload = {"target_object_id": target_object_id, "replica_type": replica_type}
        if quality_note:
            payload["quality_note"] = quality_note
        return self._emit("REPLICA_DESIGNATED", "puppet_object", replica_id, payload,
                          occurred_at=occurred_at, summary="指定为表演替身")

    # ---- 角色、人员、资格 ----

    def define_role(self, role_id: str, *, name: str, role_kind: str,
                    note: str | None = None, occurred_at: str | None = None) -> dict:
        payload = {"name": name, "role_kind": role_kind}
        if note:
            payload["note"] = note
        return self._emit("ROLE_DEFINED", "role", role_id, payload,
                          occurred_at=occurred_at, summary=f"角色：{name}")

    def register_person(self, person_id: str, *, name: str, is_minor: bool,
                        birth_year: int | None = None, contact: str | None = None,
                        apprentice_of: str | None = None, note: str | None = None,
                        occurred_at: str | None = None) -> dict:
        payload = {"name": name, "is_minor": is_minor}
        for key, value in (("birth_year", birth_year), ("contact", contact),
                           ("apprentice_of", apprentice_of), ("note", note)):
            if value is not None:
                payload[key] = value
        return self._emit("PERSON_REGISTERED", "person", person_id, payload,
                          occurred_at=occurred_at, summary=f"人员建档：{name}")

    def grant_role_qualification(self, person_id: str, *, role_id: str,
                                 status: str = "active", occurred_at: str | None = None,
                                 note: str | None = None) -> dict:
        payload = {"role_id": role_id, "status": status}
        if note:
            payload["note"] = note
        return self._emit("ROLE_QUALIFICATION_GRANTED", "person", person_id, payload,
                          occurred_at=occurred_at, summary="角色资格登记/变更")

    def grant_accompaniment_qualification(self, person_id: str, *, instrument_id: str,
                                          status: str = "active",
                                          occurred_at: str | None = None,
                                          note: str | None = None) -> dict:
        payload = {"instrument_id": instrument_id, "status": status}
        if note:
            payload["note"] = note
        return self._emit("ACCOMPANIMENT_QUALIFICATION_GRANTED", "person", person_id,
                          payload, occurred_at=occurred_at, summary="伴奏资格登记/变更")

    def change_member_status(self, person_id: str, *, status: str, reason: str,
                             occurred_at: str) -> dict:
        return self._emit("MEMBER_STATUS_CHANGED", "person", person_id,
                          {"status": status, "reason": reason}, occurred_at=occurred_at,
                          summary=f"人员状态变更：{status}")

    # ---- 乐器 ----

    def register_instrument(self, instrument_id: str, *, name: str, instrument_kind: str,
                            transport_note: str | None = None,
                            occurred_at: str | None = None) -> dict:
        payload = {"name": name, "instrument_kind": instrument_kind}
        if transport_note:
            payload["transport_note"] = transport_note
        return self._emit("INSTRUMENT_REGISTERED", "instrument", instrument_id, payload,
                          occurred_at=occurred_at, summary=f"乐器建档：{name}")

    def change_instrument_status(self, instrument_id: str, *, status: str, reason: str,
                                 occurred_at: str, transport_note: str | None = None) -> dict:
        payload = {"status": status, "reason": reason}
        if transport_note:
            payload["transport_note"] = transport_note
        return self._emit("INSTRUMENT_STATUS_CHANGED", "instrument", instrument_id,
                          payload, occurred_at=occurred_at, summary=f"乐器状态：{status}")

    # ---- 节目、剧目版本与审定 ----

    def define_program(self, program_id: str, *, title: str, cast_requirements: list,
                       accompaniment_requirements: list,
                       required_object_ids: list | None = None,
                       note: str | None = None, occurred_at: str | None = None) -> dict:
        payload = {"title": title, "cast_requirements": cast_requirements,
                   "accompaniment_requirements": accompaniment_requirements,
                   "required_object_ids": required_object_ids or []}
        if note:
            payload["note"] = note
        return self._emit("PROGRAM_MIN_STAFF_DEFINED", "program", program_id, payload,
                          occurred_at=occurred_at, summary=f"节目与最低阵容：{title}")

    def create_script_version(self, version_id: str, *, program_id: str, title: str,
                              version_label: str, lineage: str, lyrics_source: str,
                              based_on_version_id: str | None = None,
                              synopsis: str | None = None,
                              public_synopsis: str | None = None,
                              occurred_at: str | None = None) -> dict:
        payload = {"program_id": program_id, "title": title,
                   "version_label": version_label, "lineage": lineage,
                   "lyrics_source": lyrics_source}
        for key, value in (("based_on_version_id", based_on_version_id),
                           ("synopsis", synopsis), ("public_synopsis", public_synopsis)):
            if value is not None:
                payload[key] = value
        return self._emit("SCRIPT_VERSION_CREATED", "repertoire_version", version_id,
                          payload, occurred_at=occurred_at,
                          summary=f"剧目版本：{title} {version_label}")

    def approve_lyrics(self, version_id: str, *, lyrics_source: str, decision: str,
                       approved_by: str, occurred_at: str, note: str | None = None) -> dict:
        payload = {"lyrics_source": lyrics_source, "decision": decision,
                   "approved_by": approved_by}
        if note:
            payload["note"] = note
        return self._emit("LYRICS_APPROVED", "repertoire_version", version_id, payload,
                          occurred_at=occurred_at, summary=f"唱词来源审定：{decision}")

    def approve_occasion(self, version_id: str, *, occasion: str, decision: str,
                         approved_by: str, occurred_at: str,
                         conditions: str | None = None) -> dict:
        payload = {"occasion": occasion, "decision": decision, "approved_by": approved_by}
        if conditions:
            payload["conditions"] = conditions
        return self._emit("OCCASION_APPROVED", "repertoire_version", version_id, payload,
                          occurred_at=occurred_at, summary=f"适用场合审定：{occasion} {decision}")

    # ---- 场地、排班、出行 ----

    def record_venue(self, venue_id: str, *, name: str, performance_date: str,
                     conditions: dict, transport_access: str | None = None,
                     contact: str | None = None, occurred_at: str | None = None) -> dict:
        payload = {"name": name, "performance_date": performance_date,
                   "conditions": conditions}
        if transport_access:
            payload["transport_access"] = transport_access
        if contact:
            payload["contact"] = contact
        return self._emit("VENUE_CONDITIONS_RECORDED", "venue", venue_id, payload,
                          occurred_at=occurred_at, summary=f"场地条件：{name}")

    def confirm_roster(self, roster_id: str, *, program_id: str, version_id: str,
                       venue_id: str, performance_date: str, occasion: str,
                       venue_confirmed: bool, object_ids: list | None = None,
                       confirmed_by: str | None = None, occurred_at: str | None = None,
                       note: str | None = None) -> dict:
        payload = {"program_id": program_id, "version_id": version_id,
                   "venue_id": venue_id, "performance_date": performance_date,
                   "occasion": occasion, "venue_confirmed": venue_confirmed,
                   "object_ids": object_ids or []}
        if confirmed_by:
            payload["confirmed_by"] = confirmed_by
        if note:
            payload["note"] = note
        return self._emit("ROSTER_CONFIRMED", "performance_roster", roster_id, payload,
                          occurred_at=occurred_at, summary="排班确认")

    def issue_trip_plan(self, trip_id: str, roster_id: str, *, issued_by: str,
                        occurred_at: str) -> dict:
        """生成并固化真正可用的下乡计划；不可行时拒绝并给出全部阻断原因。"""
        plan = build_trip_plan(self.state, roster_id)
        if not plan["feasible"]:
            raise DomainRuleError("出行计划不可签发：" + "；".join(plan["blocks"]))
        payload = {
            "roster_id": roster_id,
            "objects": [item for item in plan["objects"] if item["load_id"]],
            "cast": [a for row in plan["cast"] for a in row["assigned"]],
            "accompanists": [a for row in plan["accompaniment"] for a in row["assigned"]],
            "transport": plan["transport"],
            "issued_by": issued_by,
        }
        if plan["warnings"]:
            payload["note"] = "；".join(plan["warnings"])
        return self._emit("TRIP_PLAN_ISSUED", "trip", trip_id, payload,
                          occurred_at=occurred_at, summary="签发下乡节目/人员/运输清单")

    def feasible_programs(self, venue_id: str, occasion: str) -> list[dict]:
        return feasible_programs_for_venue(self.state, venue_id, occasion)

    def trip_plan(self, roster_id: str) -> dict:
        return build_trip_plan(self.state, roster_id)

    # ---- 出入库与演出 ----

    def checkout(self, trip_id: str, object_id: str, *, handler: str,
                 expected_return_at: str, occurred_at: str,
                 handoff_id: str | None = None, substitute_for: str | None = None) -> dict:
        state = self.state
        violations = checkout_violations(state, {"trip_id": trip_id, "object_id": object_id})
        if violations:
            raise DomainRuleError("出库被拦截：" + "；".join(violations))
        trip = state.trips[trip_id]
        planned_ids = {
            item["load_id"] for item in trip["objects"]
            if isinstance(item, dict) and item.get("load_id")
        }
        if object_id not in planned_ids:
            raise DomainRuleError(f"「{object_id}」不在出行 {trip_id} 的装车清单内")
        handoff_id = handoff_id or f"handoff-{trip_id}-{object_id}"
        payload = {"trip_id": trip_id, "object_id": object_id, "handler": handler,
                   "expected_return_at": expected_return_at}
        if substitute_for:
            payload["substitute_for"] = substitute_for
        return self._emit("OBJECT_CHECKED_OUT", "loan_handoff", handoff_id, payload,
                          occurred_at=occurred_at, summary="出库装车")

    def return_object(self, handoff_id: str, *, returned_at: str,
                      condition_on_return: str, note: str | None = None,
                      photo_uris: list | None = None) -> dict:
        state = self.state
        handoff = state.handoffs.get(handoff_id)
        if handoff is None:
            raise DomainRuleError(f"交接记录不存在：{handoff_id}")
        if handoff["returned_at"] is not None:
            raise DomainRuleError(f"{handoff_id} 已闭环归还，不能重复归还（更正请追加记录）")
        payload = {"returned_at": returned_at,
                   "condition_on_return": condition_on_return}
        if note:
            payload["note"] = note
        if photo_uris:
            payload["photo_uris"] = photo_uris
        return self._emit("OBJECT_RETURNED", "loan_handoff", handoff_id, payload,
                          occurred_at=returned_at, summary="归还入库")

    def log_performance(self, roster_id: str, *, trip_id: str, performed_at: str,
                        attendance: int | None = None, note: str | None = None) -> dict:
        payload = {"trip_id": trip_id, "performed_at": performed_at}
        if attendance is not None:
            payload["attendance"] = attendance
        if note:
            payload["note"] = note
        return self._emit("PERFORMANCE_LOGGED", "performance_roster", roster_id, payload,
                          occurred_at=performed_at, summary="实际演出记录")

    def closure(self, trip_id: str, now: str | None = None) -> dict:
        return return_closure(self.state, trip_id, now)

    # ---- 公开扫码 ----

    def publish_public_profile(self, aggregate_type: str, aggregate_id: str, *,
                               profile_kind: str, title: str, story: str,
                               craft_note: str | None = None,
                               public_photo_uris: list | None = None,
                               occurred_at: str | None = None) -> dict:
        # 写入时 EventStore 会再做一次脱敏校验。
        payload = {"profile_kind": profile_kind, "title": title, "story": story,
                   "public_photo_uris": public_photo_uris or []}
        if craft_note:
            payload["craft_note"] = craft_note
        try:
            return self._emit("PUBLIC_PROFILE_PUBLISHED", aggregate_type, aggregate_id,
                              payload, occurred_at=occurred_at,
                              summary=f"公开扫码资料：{title}")
        except ContractError as exc:
            raise DomainRuleError(str(exc)) from exc

    def public_card(self, aggregate_type: str, aggregate_id: str) -> dict | None:
        return public_card(self.state, aggregate_type, aggregate_id)

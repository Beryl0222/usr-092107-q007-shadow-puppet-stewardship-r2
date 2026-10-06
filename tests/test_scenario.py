"""围绕“下乡前排练险把明清老皮影装车”场景的端到端测试。"""
import unittest

from src.app import DomainRuleError, TroupeSystem
from src.domain import (
    build_trip_plan, check_min_staff, public_card, version_stage_ready,
)
from src.event_store import EventStore
from src.projection import build_state
from src.seed import (
    INST_GONG, OBJ_MU, OBJ_SCREEN, OBJ_SHE, OBJ_SHE_HEAD, PROG_FAN, PROG_TEA,
    P_LI, P_TIAN, P_WANG, P_XIANG, P_ZHOU, REP_MU, REP_SHE, ROLE_BACKUP,
    ROSTER_FAN, TRIP_FAN, VENUE_MAPING, VER_FAN, VER_TEA, bootstrap,
)


class CollectionAndConservationTest(unittest.TestCase):
    def setUp(self):
        self.system = bootstrap()
        self.state = self.system.state

    def test_object_material_era_and_components(self):
        she = self.state.objects[OBJ_SHE]
        self.assertEqual(she["material"], "驴皮硝制雕刻")
        self.assertEqual(she["era"], "明代")
        self.assertEqual(she["use_policy"], "research")
        self.assertIn(OBJ_SHE_HEAD, she["components"])
        self.assertEqual(self.state.objects[OBJ_SHE_HEAD]["parent_object_id"], OBJ_SHE)

    def test_repair_photos_accumulate_but_never_disappear(self):
        repair = self.state.objects[OBJ_SHE]["repairs"][0]
        self.assertEqual(len(repair["before_photos"]), 2)
        self.assertEqual(
            {p["uri"] for p in repair["after_photos"]},
            {"photo://repair-2026-001/after-1", "photo://repair-2026-001/after-2"},
        )
        self.assertEqual(repair["status"], "completed")

    def test_replica_links_both_directions(self):
        self.assertEqual(self.state.objects[REP_SHE]["replica_of"], OBJ_SHE)
        self.assertIn(REP_SHE, self.state.objects[OBJ_SHE]["replicas"])
        self.assertIn(REP_MU, self.state.objects[OBJ_MU]["replicas"])


class MinimumStaffTest(unittest.TestCase):
    def test_during_gong_faulty_and_absences_show_is_infeasible(self):
        # 截取 10月16日0点之前的事件：田老退休、学徒请假、大锣故障均已发生，锣未修
        events = [e for e in bootstrap().store.events
                  if e["occurred_at"] < "2026-10-16T00:00:00+08:00"]
        state = build_state(events)
        result = check_min_staff(state, PROG_FAN)
        self.assertFalse(result["feasible"])
        joined = "；".join(result["blocks"])
        self.assertIn("大锣", joined)
        self.assertIn("faulty", joined)
        # 副签手仅剩李姐（学徒请假），但需1人仍够；主签手向师傅在岗
        backup_row = next(r for r in result["cast"] if r["role_id"] == ROLE_BACKUP)
        self.assertEqual(backup_row["available"], 1)

    def test_after_gong_repaired_show_is_feasible(self):
        result = check_min_staff(bootstrap().state, PROG_FAN)
        self.assertTrue(result["feasible"], result["blocks"])
        gong = next(r for r in result["accompaniment"] if r["instrument_id"] == INST_GONG)
        self.assertEqual(gong["instrument_status"], "available")
        self.assertEqual(gong["assigned"], [P_WANG])
        lead = next(r for r in result["cast"] if r["role_name"] == "主签手")
        self.assertEqual(lead["assigned"], [P_XIANG])
        self.assertNotIn(P_TIAN, lead["assigned"])  # 高龄退出后不再排班

    def test_retired_and_minor_leave_excluded_from_eligibility(self):
        state = bootstrap().state
        self.assertEqual(state.persons[P_TIAN]["status"], "retired")
        self.assertEqual(state.persons[P_ZHOU]["status"], "apprentice_leave")
        backup = [p["id"] for p in state.persons.values()
                  if p["status"] == "active"
                  and p["role_qualifications"].get(ROLE_BACKUP) == "active"]
        self.assertEqual(backup, [P_LI])


class ScriptApprovalTest(unittest.TestCase):
    def test_lyrics_and_occasion_are_separate_approvals(self):
        system = TroupeSystem()
        # 只过唱词审定、未过场合审定：仍不能上演
        system.define_program("p1", title="戏", cast_requirements=[],
                              accompaniment_requirements=[])
        system.create_script_version(
            "v1", program_id="p1", title="戏", version_label="v1",
            lineage="traditional", lyrics_source="老唱本",
            occurred_at="2026-09-30T10:00:00+08:00")
        system.approve_lyrics("v1", lyrics_source="老唱本", decision="approved",
                              approved_by="审定组", occurred_at="2026-10-01T10:00:00+08:00")
        ok, blocks = version_stage_ready(system.state.versions["v1"], "countryside_tour")
        self.assertFalse(ok)
        self.assertTrue(any("场合审定" in b for b in blocks))

    def test_traditional_and_adaptation_share_roles_but_have_own_versions(self):
        state = bootstrap().state
        self.assertEqual(state.versions[VER_FAN]["lineage"], "traditional")
        self.assertEqual(state.versions[VER_TEA]["lineage"], "new_era_adaptation")
        self.assertEqual(state.versions[VER_TEA]["based_on_version_id"], VER_FAN)
        # 两个版本的唱词来源分别由不同审定主体通过
        self.assertEqual(state.versions[VER_FAN]["lyrics_approval"]["decision"], "approved")
        self.assertEqual(state.versions[VER_TEA]["lyrics_approval"]["decision"], "approved")
        self.assertNotEqual(
            state.versions[VER_FAN]["lyrics_approval"]["lyrics_source"],
            state.versions[VER_TEA]["lyrics_approval"]["lyrics_source"])
        # 共用同一批角色与节目最低阵容结构
        fan = check_min_staff(state, PROG_FAN)
        tea = check_min_staff(state, PROG_TEA)
        self.assertTrue(fan["feasible"] and tea["feasible"])


class TripPlanTest(unittest.TestCase):
    def setUp(self):
        self.system = bootstrap()

    def test_old_objects_are_substituted_in_load_list(self):
        plan = build_trip_plan(self.system.state, ROSTER_FAN)
        self.assertTrue(plan["feasible"], plan["blocks"])
        statuses = {item["requested_id"]: item for item in plan["objects"]}
        # 明代 research 老影偶 → 替身
        self.assertEqual(statuses[OBJ_SHE]["status"], "replaced")
        self.assertEqual(statuses[OBJ_SHE]["load_id"], REP_SHE)
        # 清代 controlled_display 老影偶下乡 → 替身
        self.assertEqual(statuses[OBJ_MU]["status"], "replaced")
        self.assertEqual(statuses[OBJ_MU]["load_id"], REP_MU)
        # 现代道具与影窗照常
        self.assertEqual(statuses[OBJ_SCREEN]["status"], "loaded")
        self.assertTrue(any("佘太君" in w for w in plan["warnings"]))

    def test_plan_carries_people_and_transport(self):
        plan = build_trip_plan(self.system.state, ROSTER_FAN)
        people = {a for row in plan["cast"] for a in row["assigned"]}
        self.assertEqual(people, {P_XIANG, P_LI})  # 主唱位由向师傅/李姐满足其一
        players = {a for row in plan["accompaniment"] for a in row["assigned"]}
        self.assertEqual(players, {P_WANG})
        transport_text = " ".join(t["requirement"] for t in plan["transport"])
        self.assertIn("限高2.8米", transport_text)

    def test_venue_unconfirmed_blocks_plan(self):
        system = bootstrap()
        system.confirm_roster(
            "roster-unconfirmed", program_id=PROG_FAN, version_id=VER_FAN,
            venue_id=VENUE_MAPING, performance_date="2026-10-20",
            occasion="countryside_tour", venue_confirmed=False,
            object_ids=[OBJ_SCREEN], occurred_at="2026-10-16T15:30:00+08:00")
        plan = build_trip_plan(system.state, "roster-unconfirmed")
        self.assertFalse(plan["feasible"])
        self.assertTrue(any("场地方尚未确认" in b for b in plan["blocks"]))
        with self.assertRaises(DomainRuleError):
            system.issue_trip_plan("trip-x", "roster-unconfirmed", issued_by="向师傅",
                                   occurred_at="2026-10-16T16:00:00+08:00")

    def test_feasible_programs_for_confirmed_venue(self):
        picks = bootstrap().feasible_programs(VENUE_MAPING, "countryside_tour")
        titles = {(p["title"], p["version_label"]) for p in picks}
        self.assertIn(("樊江关", "田氏口述本·1986整理"), titles)
        self.assertIn(("鹤峰新风·茶山趣事", "2024县文化馆改编本"), titles)


class CheckoutAndClosureTest(unittest.TestCase):
    def setUp(self):
        self.system = bootstrap()
        self.system.issue_trip_plan(TRIP_FAN, ROSTER_FAN, issued_by="向师傅",
                                    occurred_at="2026-10-16T16:00:00+08:00")

    def test_old_object_checkout_is_blocked(self):
        with self.assertRaises(DomainRuleError) as ctx:
            self.system.checkout(TRIP_FAN, OBJ_SHE, handler="向师傅",
                                 expected_return_at="2026-10-17T22:00:00+08:00",
                                 occurred_at="2026-10-17T07:30:00+08:00")
        self.assertIn("研究", str(ctx.exception))

    def test_object_not_in_plan_cannot_be_loaded(self):
        with self.assertRaises(DomainRuleError):
            self.system.checkout(TRIP_FAN, OBJ_MU, handler="向师傅",
                                 expected_return_at="2026-10-17T22:00:00+08:00",
                                 occurred_at="2026-10-17T07:31:00+08:00")

    def test_double_checkout_blocked(self):
        self.system.checkout(TRIP_FAN, REP_SHE, handler="向师傅",
                             expected_return_at="2026-10-17T22:00:00+08:00",
                             occurred_at="2026-10-17T07:40:00+08:00",
                             substitute_for=OBJ_SHE)
        with self.assertRaises(DomainRuleError):
            self.system.checkout("trip-other", REP_SHE, handler="李姐",
                                 expected_return_at="2026-10-18T22:00:00+08:00",
                                 occurred_at="2026-10-17T08:00:00+08:00")

    def test_full_trip_checkout_performance_and_closure(self):
        trip = self.system.state.trips[TRIP_FAN]
        loaded = [item["load_id"] for item in trip["objects"]]
        for object_id in loaded:
            self.system.checkout(TRIP_FAN, object_id, handler="向师傅",
                                 expected_return_at="2026-10-17T22:00:00+08:00",
                                 occurred_at="2026-10-17T07:40:00+08:00")
        before = self.system.closure(TRIP_FAN)
        self.assertFalse(before["all_closed"])
        self.assertTrue(all(i["status"] == "outstanding" for i in before["items"]))

        self.system.log_performance(ROSTER_FAN, trip_id=TRIP_FAN,
                                    performed_at="2026-10-17T19:30:00+08:00",
                                    attendance=260)
        for object_id in loaded:
            self.system.return_object(
                f"handoff-{TRIP_FAN}-{object_id}",
                returned_at="2026-10-17T21:40:00+08:00", condition_on_return="完好")
        after = self.system.closure(TRIP_FAN)
        self.assertTrue(after["all_closed"])
        self.assertTrue(all(i["status"] == "returned" for i in after["items"]))
        self.assertEqual(
            len(self.system.state.rosters[ROSTER_FAN]["performances"]), 1)

    def test_duplicate_return_rejected(self):
        self.system.checkout(TRIP_FAN, REP_SHE, handler="向师傅",
                             expected_return_at="2026-10-17T22:00:00+08:00",
                             occurred_at="2026-10-17T07:40:00+08:00")
        handoff = f"handoff-{TRIP_FAN}-{REP_SHE}"
        self.system.return_object(handoff, returned_at="2026-10-17T21:40:00+08:00",
                                  condition_on_return="完好")
        with self.assertRaises(DomainRuleError):
            self.system.return_object(handoff, returned_at="2026-10-17T21:45:00+08:00",
                                      condition_on_return="完好")


class PublicCardTest(unittest.TestCase):
    def setUp(self):
        self.system = bootstrap()
        self.card = self.system.public_card("puppet_object", OBJ_SHE)

    def test_card_keeps_only_whitelisted_fields(self):
        for forbidden in ("storage_location", "contact", "is_minor", "birth_year",
                          "private_note", "diseases", "assessments"):
            self.assertNotIn(forbidden, self.card)
        self.assertEqual(self.card["name"], "佘太君影偶（明代传世）")
        self.assertTrue(self.card["stories"])

    def test_only_disclosed_repair_craft_is_shown_without_photos_or_notes(self):
        # 复检事件将该修缮的工艺审定为可公开：公开卡出现工艺条目，
        # 但修复前后照片与未公开私注一律不出现。
        craft = self.card.get("conservation_craft")
        self.assertIsNotNone(craft)
        self.assertEqual(len(craft), 1)
        self.assertEqual(craft[0]["method"], "传统鱼鳔拼贴 + 衬皮加固")
        self.assertNotIn("before_photos", craft[0])
        self.assertNotIn("after_photos", craft[0])
        self.assertNotIn("private_note", craft[0])

    def test_undisclosed_repair_photos_remain_internal(self):
        repair = self.system.state.objects[OBJ_SHE]["repairs"][0]
        # 照片在内部档案中完整保留，但不会出现在公开卡任何位置
        internal_keys = {"before_photos", "after_photos", "private_note"}
        for story in self.card["stories"]:
            self.assertTrue(internal_keys.isdisjoint(story))
        self.assertTrue(repair["before_photos"])

    def test_person_card_unavailable(self):
        self.assertIsNone(public_card(self.system.state, "person", P_ZHOU))

    def test_publishing_leaky_profile_is_rejected(self):
        with self.assertRaises(DomainRuleError):
            self.system.publish_public_profile(
                "puppet_object", OBJ_SCREEN, profile_kind="object",
                title="影窗", story="库位在道具架B-08，联系人手机号13800000000",
                occurred_at="2026-10-09T10:00:00+08:00")


if __name__ == "__main__":
    unittest.main()

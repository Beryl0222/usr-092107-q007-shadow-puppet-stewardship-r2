import json
import unittest
from pathlib import Path

from src.validator import assess_feasibility, validate_event, validate_log

ROOT = Path(__file__).parents[1]


def load_sample_log() -> list[dict]:
    return json.loads((ROOT / "data" / "sample_log.json").read_text(encoding="utf-8"))


def make_event(event_type: str, aggregate_type: str, aggregate_id: str, version: int, payload: dict) -> dict:
    return {
        "event_id": f"test-{event_type}-{aggregate_id}-v{version}",
        "event_type": event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "occurred_at": "2026-10-01T09:00:00+08:00",
        "version": version,
        "summary": "测试事件",
        "payload": payload,
    }


def heritage_object() -> list[dict]:
    return [
        make_event("OBJECT_REGISTERED", "puppet_object", "obj-old", 1,
                   {"component": "头茬", "material": "牛皮", "era": "明代"}),
        make_event("OBJECT_CLASSIFIED", "puppet_object", "obj-old", 2,
                   {"usage_class": "heritage_research_only"}),
    ]


class ContractTest(unittest.TestCase):
    def test_sample_matches_envelope(self) -> None:
        sample = json.loads((ROOT / "data" / "sample.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_event(sample), [])

    def test_sample_log_is_valid_and_closed_loop(self) -> None:
        log = load_sample_log()
        for event in log:
            self.assertEqual(validate_event(event), [], event["event_id"])
        self.assertEqual(validate_log(log), [])


class HeritageProtectionTest(unittest.TestCase):
    def test_heritage_object_cannot_be_checked_out_for_performance(self) -> None:
        log = heritage_object() + [
            make_event("OBJECT_CHECKED_OUT", "loan_handoff", "loan-1", 1,
                       {"object_id": "obj-old", "purpose": "performance",
                        "custodian": "道具组长", "expected_return_at": "2026-10-09"}),
        ]
        errors = validate_log(log)
        self.assertTrue(any("仅可用于研究或受控展示" in e for e in errors))

    def test_heritage_object_can_be_checked_out_for_research(self) -> None:
        log = heritage_object() + [
            make_event("OBJECT_CHECKED_OUT", "loan_handoff", "loan-1", 1,
                       {"object_id": "obj-old", "purpose": "research",
                        "custodian": "研究员", "expected_return_at": "2026-10-09"}),
            make_event("OBJECT_CHECKED_IN", "loan_handoff", "loan-1", 2,
                       {"object_id": "obj-old", "returned_by": "研究员", "condition_on_return": "完好"}),
        ]
        self.assertEqual(validate_log(log), [])

    def test_heritage_object_cannot_enter_transport_manifest(self) -> None:
        log = heritage_object() + [
            make_event("TRANSPORT_MANIFEST_ISSUED", "performance", "perf-1", 1,
                       {"performance_id": "perf-1", "object_ids": ["obj-old"]}),
        ]
        errors = validate_log(log)
        self.assertTrue(any("不得进入运输清单" in e for e in errors))

    def test_repair_requires_before_and_after_photos(self) -> None:
        event = make_event("REPAIR_DOCUMENTED", "puppet_object", "obj-old", 3,
                           {"method": "皮胶粘接", "before_photo_ids": [], "after_photo_ids": ["p1"]})
        self.assertTrue(any("修缮前后照片" in e for e in validate_event(event)))


class MinimumCastTest(unittest.TestCase):
    def setUp(self) -> None:
        self.base = [
            make_event("ROLE_QUALIFICATION_GRANTED", "artist", "a1", 1, {"role_id": "role-laosheng"}),
            make_event("ACCOMPANIMENT_QUALIFICATION_GRANTED", "artist", "a2", 1, {"instrument_type": "鼓"}),
            make_event("INSTRUMENT_STATUS_CHANGED", "instrument", "inst-1", 1,
                       {"instrument_type": "鼓", "status": "operational"}),
        ]
        self.cast = {"roles": {"role-laosheng": 1}, "instruments": {"鼓": 1}}
        self.entries = [
            {"artist_id": "a1", "role_id": "role-laosheng"},
            {"artist_id": "a2", "instrument_type": "鼓"},
        ]

    def roster(self, entries: list[dict], cast: dict | None = None) -> dict:
        return make_event("ROSTER_CONFIRMED", "performance_roster", "roster-1", 1, {
            "performance_id": "perf-1", "repertoire_version_id": "rep-1",
            "minimum_cast": cast or self.cast, "entries": entries,
        })

    def test_full_roster_is_feasible(self) -> None:
        self.assertEqual(validate_log(self.base + [self.roster(self.entries)]), [])

    def test_retired_artist_breaks_feasibility(self) -> None:
        log = self.base + [
            make_event("ARTIST_AVAILABILITY_CHANGED", "artist", "a1", 2, {"status": "retired"}),
            self.roster(self.entries),
        ]
        errors = validate_log(log)
        self.assertTrue(any("role-laosheng" in e and "最低阵容" in e for e in errors))

    def test_faulty_instrument_breaks_feasibility(self) -> None:
        log = self.base + [
            make_event("INSTRUMENT_STATUS_CHANGED", "instrument", "inst-1", 2,
                       {"instrument_type": "鼓", "status": "faulty"}),
            self.roster(self.entries),
        ]
        errors = validate_log(log)
        self.assertTrue(any("鼓" in e and "完好" in e for e in errors))

    def test_unqualified_artist_does_not_count(self) -> None:
        entries = [{"artist_id": "a1", "role_id": "role-dan"}, *self.entries[1:]]
        cast = {"roles": {"role-dan": 1}, "instruments": {"鼓": 1}}
        errors = validate_log(self.base + [self.roster(entries, cast)])
        self.assertTrue(any("role-dan" in e for e in errors))

    def test_assess_feasibility_function(self) -> None:
        problems = assess_feasibility(
            {"roles": {"r": 1}, "instruments": {"鼓": 1}},
            [{"artist_id": "a1", "role_id": "r"}, {"artist_id": "a2", "instrument_type": "鼓"}],
            role_qualified={("a1", "r")},
            accompaniment_qualified={("a2", "鼓")},
            available={"a1"},
            instruments_ok={"鼓": 0},
        )
        self.assertEqual(len(problems), 2)  # a2 缺勤致鼓伴奏不足，且鼓无完好件


class ClosedLoopTest(unittest.TestCase):
    def checkout(self) -> dict:
        return make_event("OBJECT_CHECKED_OUT", "loan_handoff", "loan-1", 1,
                          {"object_id": "obj-9", "purpose": "performance",
                           "custodian": "道具组长", "expected_return_at": "2026-10-09"})

    def test_checkout_without_checkin_is_reported(self) -> None:
        errors = validate_log([self.checkout()])
        self.assertTrue(any("未闭环归还" in e for e in errors))

    def test_double_checkout_is_rejected(self) -> None:
        second = self.checkout() | {"event_id": "test-double", "version": 2}
        errors = validate_log([self.checkout(), second])
        self.assertTrue(any("尚未归还不能再次出库" in e for e in errors))

    def test_checkin_without_checkout_is_rejected(self) -> None:
        event = make_event("OBJECT_CHECKED_IN", "loan_handoff", "loan-1", 1,
                           {"object_id": "obj-9", "returned_by": "道具组长", "condition_on_return": "完好"})
        self.assertTrue(any("未出库却登记归还" in e for e in validate_log([event])))


class PublicContentTest(unittest.TestCase):
    def publish(self, payload: dict) -> dict:
        return make_event("PUBLIC_QR_CONTENT_PUBLISHED", "public_qr_content", "qr-1", 1, payload)

    def test_story_only_content_is_allowed(self) -> None:
        event = self.publish({"story": "皮影雕刻技艺故事", "reviewed_by": "资料员"})
        self.assertEqual(validate_event(event), [])

    def test_sensitive_fields_are_rejected_even_when_nested(self) -> None:
        for leaked in (
            {"storage_location": "三号柜"},
            {"minor_artists": ["学徒甲"]},
            {"unpublished_repair_details": "补色配方"},
            {"attachments": [{"storage_location": "三号柜"}]},
        ):
            payload = {"story": "技艺故事", "reviewed_by": "资料员", **leaked}
            errors = validate_event(self.publish(payload))
            self.assertTrue(any("扫码内容不得包含" in e for e in errors), leaked)


class VersioningTest(unittest.TestCase):
    def test_version_must_increase_by_one(self) -> None:
        log = heritage_object()
        log[1]["version"] = 3
        self.assertTrue(any("版本应为 2" in e for e in validate_log(log)))

    def test_unknown_event_type_is_rejected(self) -> None:
        event = make_event("PHOTO_DELETED", "puppet_object", "obj-1", 1, {})
        self.assertTrue(any("未知事件类型" in e for e in validate_event(event)))


if __name__ == "__main__":
    unittest.main()

"""契约、存储不可变性与脱敏写入的测试。"""
import json
import tempfile
import unittest
from pathlib import Path

from src.contracts import (
    AGGREGATE_TYPES, EVENT_TYPES, ContractError, validate_event,
    validate_public_payload,
)
from src.event_store import EventStore

ROOT = Path(__file__).parents[1]


def envelope(event_type="OBJECT_CLASSIFIED", aggregate_type="puppet_object",
             aggregate_id="a1", version=1, payload=None):
    event = {
        "event_id": f"{aggregate_id}#v{version}",
        "event_type": event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "occurred_at": "2026-10-01T09:00:00+08:00",
        "version": version,
        "summary": "t",
    }
    if payload is not None:
        event["payload"] = payload
    return event


class SchemaConsistencyTest(unittest.TestCase):
    def test_domain_schema_lists_all_events_and_aggregates(self):
        schema = json.loads((ROOT / "contracts" / "domain.schema.json").read_text("utf-8"))
        self.assertEqual(set(schema["properties"]["event_type"]["enum"]), set(EVENT_TYPES))
        self.assertEqual(set(schema["properties"]["aggregate_type"]["enum"]),
                         set(AGGREGATE_TYPES))

    def test_sample_still_valid(self):
        sample = json.loads((ROOT / "data" / "sample.json").read_text("utf-8"))
        self.assertEqual(validate_event(sample), [])


class EventValidationTest(unittest.TestCase):
    def test_missing_envelope_fields(self):
        errors = validate_event({"event_id": "x"})
        missing = ("event_type", "aggregate_type", "aggregate_id", "occurred_at",
                   "version", "summary")
        self.assertEqual(len(errors), len(missing))
        for name in missing:
            self.assertTrue(any(name in e for e in errors), name)

    def test_wrong_aggregate_for_event(self):
        event = envelope(event_type="ROLE_DEFINED", aggregate_type="person")
        errors = validate_event(event)
        self.assertTrue(any("aggregate_type 应为" in e for e in errors))

    def test_payload_required_and_enum(self):
        bad = envelope(payload={"name": "x"})
        errors = validate_event(bad)
        self.assertTrue(any("payload.category 为必填" in e for e in errors))
        ok = envelope(payload={
            "name": "x", "category": "c", "material": "m", "era": "明代",
            "use_policy": "research"})
        self.assertEqual(validate_event(ok), [])
        bad_enum = envelope(payload={
            "name": "x", "category": "c", "material": "m", "era": "明代",
            "use_policy": "anything"})
        self.assertTrue(any("use_policy" in e for e in validate_event(bad_enum)))

    def test_repair_photos_need_uri_and_caption(self):
        payload = {"repair_id": "r1", "status": "in_progress", "scope": "s",
                   "method": "m", "repaired_by": "b",
                   "before_photos": [{"uri": "u"}]}
        errors = validate_event(envelope("REPAIR_DOCUMENTED", payload=payload))
        self.assertTrue(any("before_photos[0]" in e for e in errors))

    def test_bad_timestamp_and_version(self):
        event = envelope()
        event["occurred_at"] = "昨天"
        self.assertTrue(any("ISO 8601" in e for e in validate_event(event)))
        event = envelope()
        event["version"] = 0
        self.assertTrue(any("version" in e for e in validate_event(event)))


class EventStoreTest(unittest.TestCase):
    def _classified(self, aggregate_id="o1", version=1, at="2026-10-01T09:00:00+08:00"):
        return envelope(aggregate_id=aggregate_id, version=version,
                        payload={"name": "n", "category": "c", "material": "m",
                                 "era": "明代", "use_policy": "research"}) | {"occurred_at": at}

    def test_versions_must_be_contiguous(self):
        store = EventStore()
        store.append(self._classified(version=1))
        with self.assertRaises(ContractError):
            store.append(self._classified(version=3))

    def test_event_id_unique_and_time_monotonic(self):
        store = EventStore()
        store.append(self._classified(version=1, at="2026-10-02T09:00:00+08:00"))
        duplicate = self._classified(version=2)
        duplicate["event_id"] = "o1#v1"
        with self.assertRaises(ContractError):
            store.append(duplicate)
        with self.assertRaises(ContractError):
            store.append(self._classified(version=2, at="2026-10-01T08:00:00+08:00"))

    def test_records_are_not_mutated_in_place(self):
        store = EventStore()
        event = self._classified()
        store.append(event)
        with self.assertRaises(ContractError):
            store.append(event)  # 已存在 = 不能重新覆盖写入

    def test_public_profile_leak_rejected_on_append(self):
        store = EventStore()
        leak = envelope("PUBLIC_PROFILE_PUBLISHED", "puppet_object", "o2",
                        payload={"profile_kind": "object", "title": "t",
                                 "story": "藏品库位 A-01", "storage_location": "A-01"})
        with self.assertRaises(ContractError):
            store.append(leak)
        clean = envelope("PUBLIC_PROFILE_PUBLISHED", "puppet_object", "o2",
                         payload={"profile_kind": "object", "title": "t",
                                  "story": "影偶以驴皮雕刻，讲述忠勇故事。"})
        store.append(clean)

    def test_save_load_roundtrip_jsonl(self):
        store = EventStore()
        store.append(self._classified())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            store.save(path)
            reloaded = EventStore.load(path)
            self.assertEqual(len(reloaded.events), 1)
            self.assertEqual(reloaded.for_aggregate("o1")[0]["aggregate_id"], "o1")


class PublicSanitizerTest(unittest.TestCase):
    def test_blocks_internal_fields_and_markers(self):
        violations = validate_public_payload({"storage_location": "A-1"})
        self.assertTrue(any("storage_location" in v for v in violations))
        violations = validate_public_payload(
            {"profile_kind": "object", "title": "x", "story": "内有未公开修复细节"})
        self.assertTrue(any("未公开" in v for v in violations))

    def test_clean_story_passes(self):
        self.assertEqual(validate_public_payload(
            {"profile_kind": "object", "title": "影偶",
             "story": "一口道尽千古事，双手对舞百万兵。"}), [])


if __name__ == "__main__":
    unittest.main()

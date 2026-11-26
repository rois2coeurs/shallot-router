"""Tests for the trace reader: python3 -m unittest discover -s evaluation"""

import json
import tempfile
import unittest
from pathlib import Path

from traces import SCHEMA, split, summary, validate

EXAMPLE_TRACE = Path(__file__).parent / "examples" / "example_trace.jsonl"


def example_records() -> list[dict]:
    lines = EXAMPLE_TRACE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def first(records: list[dict], event: str) -> dict:
    return next(r for r in records if r["event"] == event)


class ExampleTraceTest(unittest.TestCase):
    def test_example_is_valid(self):
        self.assertEqual(validate(EXAMPLE_TRACE), [])

    def test_example_covers_every_event_type(self):
        self.assertEqual(set(split(EXAMPLE_TRACE)), set(SCHEMA))

    def test_example_is_read_by_pandas(self):
        tables = split(EXAMPLE_TRACE)
        self.assertEqual(len(tables["transfer_started"]), 1)
        receiver = tables["transfer_ended"].query("side == 'receiver'")
        self.assertEqual(receiver["outcome"].tolist(), ["complete"])
        self.assertIn("1 transmitted out of 1", summary(EXAMPLE_TRACE))


class CorruptedTraceTest(unittest.TestCase):
    def assert_detected(self, mutate, expected_error):
        records = example_records()
        mutate(records)
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            for record in records:
                f.write(json.dumps(record) + "\n")
        errors = validate(f.name)
        Path(f.name).unlink()
        self.assertTrue(any(expected_error in e for e in errors), errors)

    def test_missing_field(self):
        self.assert_detected(
            lambda rs: first(rs, "hop_attempted").pop("message_id"),
            "missing field: message_id",
        )

    def test_unknown_event_type(self):
        self.assert_detected(
            lambda rs: first(rs, "hop_attempted").update(event="hop"), "unknown event type"
        )

    def test_value_outside_enum(self):
        self.assert_detected(
            lambda rs: first(rs, "layer_built").update(direction="fwd"), "invalid field direction"
        )

    def test_file_must_be_a_sha256_digest(self):
        self.assert_detected(
            lambda rs: first(rs, "chunk_sent").update(file="478d9404-f7bb-4c3e-90b9-652eb065be37"),
            "invalid field file",
        )

    def test_time_going_backwards(self):
        self.assert_detected(lambda rs: rs[-2].update(time_ms=0), "time_ms decreases")

    def test_undeclared_device(self):
        self.assert_detected(
            lambda rs: first(rs, "hop_attempted").update(target=999), "not declared"
        )

    def test_successful_hop_to_offline_node(self):
        def mutate(records):
            off = next(
                r for r in records if r["event"] == "availability_changed" and not r["online"]
            )
            hop = next(
                r
                for r in records
                if r["event"] == "hop_attempted" and r["time_ms"] > off["time_ms"] and r["success"]
            )
            hop["target"] = off["node"]

        self.assert_detected(mutate, "which is offline")

    def test_reception_without_hop(self):
        self.assert_detected(
            lambda rs: first(rs, "relay_received").update(message_id="00"),
            "without a successful hop",
        )

    def test_truncated_trace(self):
        self.assert_detected(lambda rs: rs.pop(), "run_ended")


if __name__ == "__main__":
    unittest.main()

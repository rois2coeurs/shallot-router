"""Read and validate ShallotRouter traces (format v1, see docs/traces.md).

Usage:
    python3 evaluation/traces.py TRACE.jsonl [TRACE2.jsonl ...]

Validates each trace against the schema, then prints a summary computed with
pandas. Exits with status 1 if any trace has an error.

As a library:
    from traces import split, validate
    tables = split("trace.jsonl")     # dict: event type -> DataFrame
    errors = validate("trace.jsonl")  # list of strings, empty if valid
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

FORMAT_VERSION = 1

# --- Schema -----------------------------------------------------------------
#
# Field types:
#   "int", "float", "bool", "str", "hex", "digest", "obj"
#   ("enum", {...})        one of the given values
#   ("list", T)            list of elements of type T
#   ("null", T)            T or null
# Common fields (time_ms, node, event) are checked separately.
#
# Names follow the Rust types of shallot-types: FileId -> file,
# ChunkIndex -> index, InteractionKind -> kind, NodeDescriptor -> availability
# and published_at, FileDescriptor -> size and chunk_count, NodeId -> node_id.

EVENTS_WITHOUT_NODE = {"run_started", "run_ended"}

HEX = "hex"
DIGEST = "digest"  # SHA-256 (Digest), 64 lowercase hex characters
DIRECTION = ("enum", {"forward", "backward"})
TRANSFER_KIND = ("enum", {"chunk", "ack"})
INTERACTION_KIND = ("enum", {"Use", "Upload", "Download"})

SCHEMA: dict[str, dict[str, Any]] = {
    # Testbed
    "run_started": {"version": "int", "seed": "int", "params": "obj"},
    "device_declared": {"user": "int", "node_id": DIGEST},
    "availability_changed": {"online": "bool"},
    "run_ended": {},
    # E-squad and prediction
    # Same fields as Interaction in shallot-types
    "interaction_recorded": {
        "at": "int",
        "actor": "int",
        "kind": INTERACTION_KIND,
        "file": ("null", DIGEST),
    },
    "descriptor_published": {
        "published_at": "int",
        "availability": "float",
        "used_fallback": "bool",
    },
    "esquad_received": {
        "file": DIGEST,
        "transfer_kind": TRANSFER_KIND,
        "index": "int",
        "message_id": HEX,
        "received_via": ("enum", {"route", "esquad"}),
        "action": ("enum", {"local", "forward", "cache", "drop"}),
        "reason": ("null", ("enum", {"offline", "unknown_file", "duplicate", "bad_hash"})),
    },
    "cache_updated": {
        "file": DIGEST,
        "transfer_kind": TRANSFER_KIND,
        "index": "int",
        "operation": ("enum", {"put", "deliver", "evict", "expire"}),
        "entry_count": "int",
    },
    # Channels and routes
    "channel_offered": {
        "file": DIGEST,
        "size": "int",
        "chunk_size": "int",
        "chunk_count": "int",
        "out_of_band_bytes": "int",
    },
    "channel_accepted": {"file": DIGEST, "out_of_band_bytes": "int"},
    "layer_built": {
        "file": DIGEST,
        "direction": DIRECTION,
        "position": "int",
        "members": ("list", "int"),
        "availability": ("list", ("null", "float")),
        "predicted_unavailability": ("null", "float"),
        "stop_reason": (
            "enum",
            {"epsilon_reached", "max_size_reached", "view_exhausted", "esquad_layer"},
        ),
        "view_size": ("null", "int"),
    },
    "route_completed": {"file": DIGEST, "direction": DIRECTION, "layer_sizes": ("list", "int")},
    # Relaying
    "hop_attempted": {
        "target": "int",
        "message_id": HEX,
        "size_bytes": "int",
        "rank_in_layer": "int",
        "success": "bool",
        "context": ("enum", {"route", "esquad"}),
    },
    "relay_received": {
        "message_id": HEX,
        "size_bytes": "int",
        "decryption_attempts": "int",
        "decision": ("enum", {"forward", "deliver", "reject"}),
        "forwarded_message_id": ("null", HEX),
        "next_layer": ("null", ("list", "int")),
    },
    "message_dropped": {"message_id": HEX, "attempted_targets": "int"},
    # Transfer
    "transfer_started": {
        "file": DIGEST,
        "chunk_count": "int",
        "window_size": "int",
        "retransmit_timeout_ms": "int",
        "dead_channel_timeout_ms": "int",
    },
    "chunk_sent": {
        "file": DIGEST,
        "index": "int",
        "attempt": "int",
        "message_id": HEX,
        "header_bytes": "int",
    },
    "chunk_received": {"file": DIGEST, "index": "int", "hash_valid": "bool", "duplicate": "bool"},
    "ack_sent": {"file": DIGEST, "index": "int", "message_id": HEX, "header_bytes": "int"},
    "ack_received": {"file": DIGEST, "index": "int", "duplicate": "bool"},
    "transfer_ended": {
        "file": DIGEST,
        "side": ("enum", {"sender", "receiver"}),
        "outcome": ("enum", {"complete", "dead", "aborted"}),
        "completed_chunks": "int",
    },
}


# --- Reading ----------------------------------------------------------------


def _open(path: str | Path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def records(path: str | Path) -> Iterator[tuple[int, dict]]:
    """Yield (line number, event) for each line of the trace."""
    with _open(path) as f:
        for line_number, line in enumerate(f, start=1):
            yield line_number, json.loads(line)


def load(path: str | Path) -> pd.DataFrame:
    """Whole trace in a single DataFrame (one column per field seen)."""
    df = pd.read_json(path, lines=True, compression="infer")
    df["node"] = df["node"].astype("Int64")
    return df


def split(path: str | Path) -> dict[str, pd.DataFrame]:
    """One DataFrame per event type, with only that event's columns."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for _, record in records(path):
        groups[record["event"]].append(record)
    tables = {}
    for event, event_records in groups.items():
        df = pd.DataFrame.from_records(event_records).drop(columns="event")
        df["node"] = df["node"].astype("Int64")
        tables[event] = df
    return tables


# --- Validation -------------------------------------------------------------


def _check_type(value: Any, spec: Any) -> bool:
    if isinstance(spec, tuple):
        kind, arg = spec
        if kind == "null":
            return value is None or _check_type(value, arg)
        if kind == "list":
            return isinstance(value, list) and all(_check_type(v, arg) for v in value)
        if kind == "enum":
            return isinstance(value, str) and value in arg
        raise ValueError(spec)
    if spec == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if spec == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec == "bool":
        return isinstance(value, bool)
    if spec == "str":
        return isinstance(value, str)
    if spec == HEX:
        return isinstance(value, str) and value != "" and all(c in "0123456789abcdef" for c in value)
    if spec == DIGEST:
        return _check_type(value, HEX) and len(value) == 64
    if spec == "obj":
        return isinstance(value, dict)
    raise ValueError(spec)


def _check_record(record: dict) -> list[str]:
    errors = []
    event = record.get("event")
    if event not in SCHEMA:
        return [f"unknown event type: {event!r}"]
    time_ms = record.get("time_ms")
    if not _check_type(time_ms, "int") or time_ms < 0:
        errors.append(f"invalid time_ms: {time_ms!r}")
    if "node" not in record:
        errors.append("missing field: node")
    elif event in EVENTS_WITHOUT_NODE:
        if record["node"] is not None:
            errors.append(f"{event} must have node = null")
    elif not _check_type(record["node"], "int"):
        errors.append(f"invalid node: {record['node']!r}")
    for field, spec in SCHEMA[event].items():
        if field not in record:
            errors.append(f"missing field: {field}")
        elif not _check_type(record[field], spec):
            errors.append(f"invalid field {field}: {record[field]!r}")
    return errors


def _check_semantics(record: dict) -> list[str]:
    """Constraints between fields of the same event."""
    event = record["event"]
    errors = []
    if event == "interaction_recorded" and (record["kind"] == "Use") != (record["file"] is None):
        errors.append("interaction_recorded: file must be null for Use and only for Use")
    elif event == "layer_built":
        if not 1 <= record["position"] <= 4:
            errors.append(f"layer_built: position outside 1..4: {record['position']}")
        if len(record["availability"]) != len(record["members"]):
            errors.append("layer_built: availability and members have different lengths")
        if len(set(record["members"])) != len(record["members"]):
            errors.append("layer_built: duplicate member")
        if (record["position"] == 4) != (record["stop_reason"] == "esquad_layer"):
            errors.append("layer_built: stop_reason = esquad_layer if and only if position = 4")
    elif event == "route_completed" and len(record["layer_sizes"]) != 4:
        errors.append("route_completed: layer_sizes must have 4 elements")
    elif event == "relay_received":
        forwarded = record["decision"] == "forward"
        if forwarded != (record["forwarded_message_id"] is not None) or forwarded != (
            record["next_layer"] is not None
        ):
            errors.append(
                "relay_received: forwarded_message_id and next_layer set "
                "if and only if decision = forward"
            )
    elif event == "esquad_received":
        needs_reason = record["action"] in {"cache", "drop"}
        if needs_reason != (record["reason"] is not None):
            errors.append("esquad_received: reason set if and only if action = cache or drop")
    elif event in {"hop_attempted", "chunk_sent"}:
        key = "rank_in_layer" if event == "hop_attempted" else "attempt"
        if record[key] < 1:
            errors.append(f"{event}: {key} starts at 1")
    return errors


def validate(path: str | Path) -> list[str]:
    """Return the list of errors in the trace (empty if it is valid).

    Besides the schema of each line, checks that:
    - the first line is run_started with version FORMAT_VERSION, the last run_ended;
    - time_ms never decreases;
    - every device mentioned was declared by device_declared;
    - a successful hop targets a device that is online according to availability_changed;
    - every reception (relay_received, esquad_received via esquad) follows a
      successful hop to that node carrying the same message_id.
    """
    errors: list[str] = []
    devices: set[int] = set()
    online: dict[int, bool] = {}
    delivered: set[tuple[int, str]] = set()  # (target, message_id) of successful hops
    last_time = -1
    last_event = None
    line_count = 0

    def error(line_number: int, message: str) -> None:
        errors.append(f"line {line_number}: {message}")

    def check_declared(line_number: int, node: int, role: str) -> None:
        if node not in devices:
            error(line_number, f"{role} {node} not declared by device_declared")

    try:
        for line_number, record in records(path):
            line_count += 1
            if not isinstance(record, dict):
                error(line_number, "line is not a JSON object")
                continue
            line_errors = _check_record(record)
            if line_errors:
                for e in line_errors:
                    error(line_number, e)
                continue
            for e in _check_semantics(record):
                error(line_number, e)

            event, time_ms, node = record["event"], record["time_ms"], record["node"]
            if line_number == 1:
                if event != "run_started":
                    error(line_number, "trace must start with run_started")
                elif record["version"] != FORMAT_VERSION:
                    error(
                        line_number,
                        f"unsupported version {record['version']} (expected {FORMAT_VERSION})",
                    )
                elif not _check_type(record["params"].get("round_duration_ms"), "int"):
                    error(line_number, "run_started: params.round_duration_ms (int) missing")
            elif event == "run_started":
                error(line_number, "run_started outside the first line")
            if time_ms < last_time:
                error(line_number, f"time_ms decreases ({time_ms} < {last_time})")
            last_time, last_event = time_ms, event

            if event == "device_declared":
                devices.add(node)
                continue
            if node is not None:
                check_declared(line_number, node, "device")

            if event == "availability_changed":
                online[node] = record["online"]
            elif event == "interaction_recorded":
                check_declared(line_number, record["actor"], "actor")
            elif event == "layer_built":
                for member in record["members"]:
                    check_declared(line_number, member, "member")
            elif event == "hop_attempted":
                check_declared(line_number, record["target"], "target")
                if record["success"]:
                    if online.get(record["target"]) is False:
                        error(
                            line_number,
                            f"successful hop to {record['target']}, which is offline",
                        )
                    delivered.add((record["target"], record["message_id"]))
            elif event == "relay_received":
                if (node, record["message_id"]) not in delivered:
                    error(
                        line_number,
                        f"relay_received of {record['message_id']} "
                        f"without a successful hop to {node}",
                    )
                for member in record["next_layer"] or []:
                    check_declared(line_number, member, "member")
            elif event == "esquad_received" and record["received_via"] == "esquad":
                if (node, record["message_id"]) not in delivered:
                    error(
                        line_number,
                        f"esquad_received of {record['message_id']} "
                        f"without a successful hop to {node}",
                    )
    except json.JSONDecodeError as e:
        errors.append(f"line {line_count + 1}: invalid JSON ({e.msg})")
        return errors

    if line_count == 0:
        errors.append("empty trace")
    elif last_event != "run_ended":
        errors.append("trace does not end with run_ended (interrupted run?)")
    return errors


# --- Summary ----------------------------------------------------------------


def summary(path: str | Path) -> str:
    """A few indicators computed with pandas, to check that a trace can be read."""
    tables = split(path)
    run = tables["run_started"].iloc[0]
    lines = [f"Trace {path}", f"  format v{run['version']}, seed {run['seed']}"]

    counts = {event: len(df) for event, df in tables.items()}
    lines.append("  events: " + ", ".join(f"{e}={c}" for e, c in sorted(counts.items())))

    if "transfer_ended" in tables:
        ends = tables["transfer_ended"].pivot_table(
            index="file", columns="side", values="outcome", aggfunc="last"
        )
        starts = tables["transfer_started"].set_index("file")["time_ms"]
        received = tables["transfer_ended"].query("side == 'receiver' and outcome == 'complete'")
        received = received.set_index("file")["time_ms"]
        transmitted = received.reindex(starts.index).notna()
        lines.append(f"  transfers: {transmitted.sum()} transmitted out of {len(starts)}")
        for file in starts.index:
            duration = received.get(file, float("nan")) - starts[file]
            sides = ends.loc[file].to_dict() if file in ends.index else {}
            lines.append(
                f"    {file[:8]}… sender={sides.get('sender')} "
                f"receiver={sides.get('receiver')} duration={duration / 1000:.1f} s"
            )

    if "hop_attempted" in tables:
        rates = tables["hop_attempted"].groupby("context")["success"].mean()
        lines.append("  successful hops: " + ", ".join(f"{c} {r:.0%}" for c, r in rates.items()))

    if "chunk_sent" in tables:
        resent = (tables["chunk_sent"]["attempt"] > 1).sum()
        lines.append(f"  chunks sent: {len(tables['chunk_sent'])}, of which {resent} resent")

    if "layer_built" in tables:
        layers = tables["layer_built"].assign(size=lambda d: d["members"].str.len())
        sizes = layers.groupby("position")["size"].mean()
        lines.append(
            "  mean layer size: " + ", ".join(f"L{p}={s:.1f}" for p, s in sizes.items())
        )
        reasons = layers["stop_reason"].value_counts()
        lines.append("  PickLayer stop: " + ", ".join(f"{k}={v}" for k, v in reasons.items()))

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    status = 0
    for path in argv:
        errors = validate(path)
        if errors:
            status = 1
            print(f"{path}: {len(errors)} error(s)")
            for e in errors:
                print(f"  {e}")
            continue
        print(summary(path))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Lecture et validation des traces ShallotRouter (format v1, voir docs/traces.md).

Usage :
    python3 evaluation/traces.py TRACE.jsonl [TRACE2.jsonl ...]

Valide chaque trace contre le schéma, puis affiche un résumé calculé avec
pandas. Code de sortie 1 si une trace contient une erreur.

En bibliothèque :
    from traces import split, validate
    tables = split("trace.jsonl")      # dict ev -> DataFrame
    erreurs = validate("trace.jsonl")  # liste de chaînes, vide si conforme
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

VERSION = 1

# --- Schéma -----------------------------------------------------------------
#
# Types de champ :
#   "int", "float", "bool", "str", "hex", "obj"
#   ("enum", {...})        une des valeurs données
#   ("list", T)            liste d'éléments de type T
#   ("null", T)            T ou null
# Les champs communs (t, node, ev) sont vérifiés à part.

NODE_NULL = {"run_start", "run_end"}

HEX = "hex"
DIR = ("enum", {"fwd", "bwd"})
KIND = ("enum", {"chunk", "ack"})
TYP = ("enum", {"USE", "UL", "DL"})

SCHEMA: dict[str, dict[str, Any]] = {
    # Banc d'essai (jamais écrit par le protocole, D8)
    "run_start": {"v": "int", "seed": "int", "params": "obj"},
    "device": {"user": "int"},
    "churn": {"online": "bool"},
    "run_end": {},
    # E-squad et prédiction
    "interaction": {"typ": TYP, "did": ("null", HEX)},
    "interaction_learned": {"origin": "int", "ts": "int", "typ": TYP},
    "descriptor_published": {"round": "int", "p": "float", "fallback": "bool"},
    "esquad_rx": {
        "did": HEX,
        "kind": KIND,
        "idx": "int",
        "mid": HEX,
        "via": ("enum", {"route", "esquad"}),
        "action": ("enum", {"local", "forward", "cache", "drop"}),
        "reason": ("null", ("enum", {"offline", "unknown_did", "duplicate", "bad_hash"})),
    },
    "cache": {
        "did": HEX,
        "kind": KIND,
        "idx": "int",
        "op": ("enum", {"put", "deliver", "evict", "expire"}),
        "entries": "int",
    },
    # Canaux et routes
    "channel_offer": {
        "did": HEX,
        "size": "int",
        "chunk_size": "int",
        "chunks": "int",
        "oob_bytes": "int",
    },
    "channel_accept": {"did": HEX, "oob_bytes": "int"},
    "layer_built": {
        "did": HEX,
        "dir": DIR,
        "pos": "int",
        "members": ("list", "int"),
        "p": ("list", ("null", "float")),
        "unavail": ("null", "float"),
        "stop": ("enum", {"eps", "lmax", "view", "esquad"}),
        "view": ("null", "int"),
    },
    "route_ready": {"did": HEX, "dir": DIR, "sizes": ("list", "int")},
    # Relayage
    "hop": {
        "to": "int",
        "mid": HEX,
        "bytes": "int",
        "try": "int",
        "ok": "bool",
        "ctx": ("enum", {"route", "esquad"}),
    },
    "relay_recv": {
        "mid": HEX,
        "bytes": "int",
        "tries": "int",
        "result": ("enum", {"forward", "deliver", "reject"}),
        "out": ("null", HEX),
        "next": ("null", ("list", "int")),
    },
    "drop": {"mid": HEX, "tried": "int"},
    # Transfert
    "transfer_start": {
        "did": HEX,
        "chunks": "int",
        "window": "int",
        "rto_ms": "int",
        "dead_ms": "int",
    },
    "chunk_sent": {"did": HEX, "idx": "int", "attempt": "int", "mid": HEX, "header_bytes": "int"},
    "chunk_recv": {"did": HEX, "idx": "int", "valid": "bool", "dup": "bool"},
    "ack_sent": {"did": HEX, "idx": "int", "mid": HEX, "header_bytes": "int"},
    "ack_recv": {"did": HEX, "idx": "int", "dup": "bool"},
    "transfer_end": {
        "did": HEX,
        "side": ("enum", {"sender", "receiver"}),
        "outcome": ("enum", {"complete", "dead", "aborted"}),
        "chunks_done": "int",
    },
}

# Événements écrits par le banc d'essai seulement (D8).
TESTBED_EVENTS = {"run_start", "device", "churn", "run_end"}


# --- Lecture ----------------------------------------------------------------


def _open(path: str | Path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def records(path: str | Path) -> Iterator[tuple[int, dict]]:
    """Rend (numéro de ligne, événement) pour chaque ligne de la trace."""
    with _open(path) as f:
        for lineno, line in enumerate(f, start=1):
            yield lineno, json.loads(line)


def load(path: str | Path) -> pd.DataFrame:
    """Toute la trace dans un seul DataFrame (une colonne par champ rencontré)."""
    df = pd.read_json(path, lines=True, compression="infer")
    df["node"] = df["node"].astype("Int64")
    return df


def split(path: str | Path) -> dict[str, pd.DataFrame]:
    """Un DataFrame par type d'événement, avec seulement ses propres colonnes."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for _, rec in records(path):
        groups[rec["ev"]].append(rec)
    tables = {}
    for ev, recs in groups.items():
        df = pd.DataFrame.from_records(recs).drop(columns="ev")
        df["node"] = df["node"].astype("Int64")
        tables[ev] = df
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
    if spec == "obj":
        return isinstance(value, dict)
    raise ValueError(spec)


def _check_record(rec: dict) -> list[str]:
    errs = []
    ev = rec.get("ev")
    if ev not in SCHEMA:
        return [f"type d'événement inconnu : {ev!r}"]
    t = rec.get("t")
    if not _check_type(t, "int") or t < 0:
        errs.append(f"t invalide : {t!r}")
    if "node" not in rec:
        errs.append("champ manquant : node")
    elif ev in NODE_NULL:
        if rec["node"] is not None:
            errs.append(f"{ev} doit avoir node = null")
    elif not _check_type(rec["node"], "int"):
        errs.append(f"node invalide : {rec['node']!r}")
    for field, spec in SCHEMA[ev].items():
        if field not in rec:
            errs.append(f"champ manquant : {field}")
        elif not _check_type(rec[field], spec):
            errs.append(f"champ {field} invalide : {rec[field]!r}")
    return errs


def _check_semantics(rec: dict) -> list[str]:
    """Contraintes entre champs d'un même événement."""
    ev = rec["ev"]
    errs = []
    if ev == "interaction" and (rec["typ"] == "USE") != (rec["did"] is None):
        errs.append("interaction : did doit être null pour USE et seulement pour USE")
    elif ev == "layer_built":
        if not 1 <= rec["pos"] <= 4:
            errs.append(f"layer_built : pos hors de 1..4 : {rec['pos']}")
        if len(rec["p"]) != len(rec["members"]):
            errs.append("layer_built : p et members de longueurs différentes")
        if len(set(rec["members"])) != len(rec["members"]):
            errs.append("layer_built : membre en double")
        if (rec["pos"] == 4) != (rec["stop"] == "esquad"):
            errs.append("layer_built : stop = esquad si et seulement si pos = 4")
    elif ev == "route_ready" and len(rec["sizes"]) != 4:
        errs.append("route_ready : sizes doit avoir 4 éléments")
    elif ev == "relay_recv":
        fwd = rec["result"] == "forward"
        if fwd != (rec["out"] is not None) or fwd != (rec["next"] is not None):
            errs.append("relay_recv : out et next renseignés si et seulement si result = forward")
    elif ev == "esquad_rx":
        needs_reason = rec["action"] in {"cache", "drop"}
        if needs_reason != (rec["reason"] is not None):
            errs.append("esquad_rx : reason renseignée si et seulement si action = cache ou drop")
    elif ev in {"hop", "chunk_sent"}:
        key = "try" if ev == "hop" else "attempt"
        if rec[key] < 1:
            errs.append(f"{ev} : {key} commence à 1")
    return errs


def validate(path: str | Path) -> list[str]:
    """Rend la liste des erreurs de la trace (vide si elle est conforme).

    Vérifie, en plus du schéma de chaque ligne :
    - la première ligne est run_start en version VERSION, la dernière run_end ;
    - t ne décroît jamais ;
    - tout appareil cité a été déclaré par un événement device ;
    - un saut réussi (hop ok) vise un appareil en ligne d'après churn ;
    - toute réception (relay_recv, esquad_rx via esquad) suit un saut réussi
      vers ce nœud portant le même mid.
    """
    errors: list[str] = []
    devices: set[int] = set()
    online: dict[int, bool] = {}
    delivered: set[tuple[int, str]] = set()  # (destinataire, mid) des sauts réussis
    last_t = -1
    last_ev = None
    n = 0

    def err(lineno: int, msg: str) -> None:
        errors.append(f"ligne {lineno} : {msg}")

    def known(lineno: int, node: int, what: str) -> None:
        if node not in devices:
            err(lineno, f"{what} {node} non déclaré par un événement device")

    try:
        for lineno, rec in records(path):
            n += 1
            if not isinstance(rec, dict):
                err(lineno, "la ligne n'est pas un objet JSON")
                continue
            line_errs = _check_record(rec)
            if line_errs:
                for e in line_errs:
                    err(lineno, e)
                continue
            for e in _check_semantics(rec):
                err(lineno, e)

            ev, t, node = rec["ev"], rec["t"], rec["node"]
            if lineno == 1:
                if ev != "run_start":
                    err(lineno, "la trace doit commencer par run_start")
                elif rec["v"] != VERSION:
                    err(lineno, f"version {rec['v']} non prise en charge (attendu {VERSION})")
                elif not _check_type(rec["params"].get("T_ms"), "int"):
                    err(lineno, "run_start : params.T_ms (entier) manquant")
            elif ev == "run_start":
                err(lineno, "run_start ailleurs qu'en première ligne")
            if t < last_t:
                err(lineno, f"t décroît ({t} < {last_t})")
            last_t, last_ev = t, ev

            if ev == "device":
                devices.add(node)
                continue
            if node is not None:
                known(lineno, node, "appareil")

            if ev == "churn":
                online[node] = rec["online"]
            elif ev == "layer_built":
                for m in rec["members"]:
                    known(lineno, m, "membre")
            elif ev == "hop":
                known(lineno, rec["to"], "destinataire")
                if rec["ok"]:
                    if online.get(rec["to"]) is False:
                        err(lineno, f"saut réussi vers {rec['to']}, hors ligne d'après churn")
                    delivered.add((rec["to"], rec["mid"]))
            elif ev == "relay_recv":
                if (node, rec["mid"]) not in delivered:
                    err(lineno, f"relay_recv de {rec['mid']} sans saut réussi vers {node}")
                for m in rec["next"] or []:
                    known(lineno, m, "membre")
            elif ev == "esquad_rx" and rec["via"] == "esquad":
                if (node, rec["mid"]) not in delivered:
                    err(lineno, f"esquad_rx de {rec['mid']} sans saut réussi vers {node}")
    except json.JSONDecodeError as e:
        errors.append(f"ligne {n + 1} : JSON invalide ({e.msg})")
        return errors

    if n == 0:
        errors.append("trace vide")
    elif last_ev != "run_end":
        errors.append("la trace ne se termine pas par run_end (exécution interrompue ?)")
    return errors


# --- Résumé -----------------------------------------------------------------


def summary(path: str | Path) -> str:
    """Quelques indicateurs calculés avec pandas, pour vérifier qu'une trace se relit."""
    tb = split(path)
    run = tb["run_start"].iloc[0]
    out = [f"Trace {path}", f"  format v{run['v']}, graine {run['seed']}"]

    counts = {ev: len(df) for ev, df in tb.items()}
    out.append("  événements : " + ", ".join(f"{ev}={c}" for ev, c in sorted(counts.items())))

    if "transfer_end" in tb:
        ends = tb["transfer_end"].pivot_table(
            index="did", columns="side", values="outcome", aggfunc="last"
        )
        starts = tb["transfer_start"].set_index("did")["t"]
        recv = tb["transfer_end"].query("side == 'receiver' and outcome == 'complete'")
        recv = recv.set_index("did")["t"]
        transmitted = recv.reindex(starts.index).notna()
        out.append(f"  transferts : {transmitted.sum()} transmis sur {len(starts)}")
        for did in starts.index:
            dur = recv.get(did, float("nan")) - starts[did]
            side = ends.loc[did].to_dict() if did in ends.index else {}
            out.append(f"    {did[:8]}… émetteur={side.get('sender')} récepteur={side.get('receiver')} "
                       f"durée={dur / 1000:.1f} s")

    if "hop" in tb:
        hops = tb["hop"]
        rate = hops.groupby("ctx")["ok"].mean()
        out.append("  sauts réussis : " + ", ".join(f"{c} {r:.0%}" for c, r in rate.items()))

    if "chunk_sent" in tb:
        resent = (tb["chunk_sent"]["attempt"] > 1).sum()
        out.append(f"  chunks émis : {len(tb['chunk_sent'])} dont {resent} renvois")

    if "layer_built" in tb:
        lb = tb["layer_built"].assign(size=lambda d: d["members"].str.len())
        by = lb.groupby("pos")["size"].mean()
        out.append("  taille moyenne des couches : "
                   + ", ".join(f"L{p}={s:.1f}" for p, s in by.items()))
        stops = lb["stop"].value_counts()
        out.append("  arrêt de PickLayer : " + ", ".join(f"{k}={v}" for k, v in stops.items()))

    return "\n".join(out)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    status = 0
    for path in argv:
        errs = validate(path)
        if errs:
            status = 1
            print(f"{path} : {len(errs)} erreur(s)")
            for e in errs:
                print(f"  {e}")
            continue
        print(summary(path))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

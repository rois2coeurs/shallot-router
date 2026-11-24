"""Tests du lecteur de traces : python3 -m unittest discover -s evaluation"""

import json
import tempfile
import unittest
from pathlib import Path

from traces import SCHEMA, split, summary, validate

EXEMPLE = Path(__file__).parent / "exemples" / "trace-exemple.jsonl"


def lines():
    return EXEMPLE.read_text(encoding="utf-8").splitlines()


class TraceExemple(unittest.TestCase):
    def test_exemple_valide(self):
        self.assertEqual(validate(EXEMPLE), [])

    def test_exemple_couvre_tous_les_evenements(self):
        self.assertEqual(set(split(EXEMPLE)), set(SCHEMA))

    def test_relu_par_pandas(self):
        tb = split(EXEMPLE)
        self.assertEqual(len(tb["transfer_start"]), 1)
        recv = tb["transfer_end"].query("side == 'receiver'")
        self.assertEqual(recv["outcome"].tolist(), ["complete"])
        self.assertIn("1 transmis sur 1", summary(EXEMPLE))


class TraceCorrompue(unittest.TestCase):
    def check(self, mutate, attendu):
        recs = [json.loads(l) for l in lines()]
        mutate(recs)
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        errs = validate(f.name)
        Path(f.name).unlink()
        self.assertTrue(any(attendu in e for e in errs), errs)

    def first(self, recs, ev):
        return next(r for r in recs if r["ev"] == ev)

    def test_champ_manquant(self):
        self.check(lambda rs: self.first(rs, "hop").pop("mid"), "champ manquant : mid")

    def test_evenement_inconnu(self):
        self.check(lambda rs: self.first(rs, "hop").update(ev="saut"), "inconnu")

    def test_valeur_hors_enumeration(self):
        self.check(lambda rs: self.first(rs, "layer_built").update(dir="aller"), "dir invalide")

    def test_temps_qui_recule(self):
        self.check(lambda rs: rs[-2].update(t=0), "t décroît")

    def test_appareil_non_declare(self):
        self.check(lambda rs: self.first(rs, "hop").update(to=999), "non déclaré")

    def test_saut_reussi_vers_noeud_eteint(self):
        def mutate(rs):
            off = next(r for r in rs if r["ev"] == "churn" and not r["online"])
            hop = next(r for r in rs if r["ev"] == "hop" and r["t"] > off["t"] and r["ok"])
            hop["to"] = off["node"]

        self.check(mutate, "hors ligne d'après churn")

    def test_reception_sans_saut(self):
        self.check(lambda rs: self.first(rs, "relay_recv").update(mid="00"), "sans saut réussi")

    def test_trace_tronquee(self):
        self.check(lambda rs: rs.pop(), "run_end")


if __name__ == "__main__":
    unittest.main()

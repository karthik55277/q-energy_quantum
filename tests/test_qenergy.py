"""Checks that the energy maths, the encoding and Grover's search all behave.

Run:  python -m pytest
"""
import math
import sys
from pathlib import Path

import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qenergy import household as hh  # noqa: E402
from qenergy.grover import best_rounds, diffuser, oracle, search  # noqa: E402

APPS = hh.APPLIANCES


# ---------------- the household maths ----------------
def test_score_of_one_plan():
    # Washing machine Noon, Dishwasher Noon, Water heater Morning, EV Evening
    s = hh.score(["Noon", "Noon", "Morning", "Evening"], APPS)
    assert s["load"] == [2.0, 2.0, 3.5, 0.0]
    assert s["bill"] == pytest.approx(2 * 6 + 2 * 4 + 3.5 * 10)          # ₹55
    assert s["peak"] == 3.5
    assert s["co2"] == pytest.approx(2 * .75 + 2 * .30 + 3.5 * .85)
    assert s["solar_share"] == pytest.approx((0.5 + 2 + 0.5) / 7.5, abs=1e-4)


def test_usual_routine():
    s = hh.score(["Evening", "Evening", "Morning", "Evening"], APPS)
    assert s["bill"] == 67.0 and s["peak"] == 5.5


# ---------------- encoding ----------------
@pytest.mark.parametrize("code,slot", [("00", "Morning"), ("01", "Noon"), ("10", "Evening"), ("11", "Night")])
def test_codes(code, slot):
    assert hh.decode(code) == [slot]


def test_encode_decode_round_trip():
    for x in range(256):
        b = format(x, "08b")
        assert hh.encode(hh.decode(b)) == b
    assert hh.decode("01 01 00 11") == ["Noon", "Noon", "Morning", "Night"]


def test_bad_bitstring():
    with pytest.raises(ValueError):
        hh.decode("012")


# ---------------- the rule check (what the oracle marks) ----------------
def test_good_plans_default_limits():
    good = hh.good_plans(APPS, 45, 4.0)
    assert sorted(good) == ["00010111", "01010011", "01010111"]
    for b in good:
        s = hh.score(hh.decode(b), APPS)
        assert s["bill"] <= 45 and s["peak"] <= 4.0


def test_allowed_slot_count():
    allowed = [x for x in range(256) if hh.is_allowed(hh.decode(format(x, "08b")), APPS)]
    assert len(allowed) == 3 * 3 * 3 * 2


# ---------------- the quantum part ----------------
def test_oracle_flips_exactly_the_good_plans():
    good = hh.good_plans(APPS, 45, 4.0)
    qc = QuantumCircuit(8)
    qc.h(range(8))
    before = Statevector(qc)
    after = before.evolve(oracle(8, good))
    for x in range(256):
        b = format(x, "08b")
        expected = -before.data[x] if b in good else before.data[x]
        assert after.data[x] == pytest.approx(expected, abs=1e-9)


def test_diffuser_reflects_about_mean():
    import numpy as np
    rng = np.random.default_rng(0)
    v = rng.normal(size=8)
    v /= np.linalg.norm(v)
    out = Statevector(v).evolve(diffuser(3)).data.real
    assert np.allclose(out, 2 * v.mean() - v, atol=1e-9)


def test_best_rounds():
    assert best_rounds(256, 3) == 7
    assert best_rounds(256, 1) == 12
    assert best_rounds(256, 0) == 0


def test_search_finds_good_plan():
    r = search(APPS, 45, 4.0, shots=1000, seed=3)
    assert r["status"] == "ok" and r["n_good"] == 3 and r["rounds"] == 7
    assert r["success_rate"] > 0.95                       # vs 1.2% by random guessing
    assert abs(r["success_rate"] - r["theory_success"]) < 0.03
    assert r["picked_is_good"]
    assert r["plan_score"]["bill"] <= 45 and r["plan_score"]["peak"] <= 4.0


def test_animation_frames_match_theory():
    r = search(APPS, 45, 4.0, seed=1)
    good = set(r["good"])
    theta = math.asin(math.sqrt(3 / 256))
    diffuser_frames = [f for f in r["frames"] if f["label"] == "diffuser"]
    for f in diffuser_frames:
        p = sum(a * a for i, a in enumerate(f["amps"]) if format(i, "08b") in good)
        assert p == pytest.approx(math.sin((2 * f["round"] + 1) * theta) ** 2, abs=1e-4)


def test_no_good_plan():
    r = search(APPS, 41, 3.5)
    assert r["status"] == "none"


def test_bad_input():
    with pytest.raises(ValueError):
        search([{"name": "Heater", "kw": -1, "allowed": ["Noon"]}], 45, 4)


# ---------------- the web app ----------------
def test_api():
    from app import app
    c = app.test_client()
    assert c.get("/").status_code == 200
    assert len(c.get("/api/household").get_json()["appliances"]) == 4
    r = c.post("/api/search", json={"max_bill": 45, "max_peak": 4})
    assert r.status_code == 200 and r.get_json()["status"] == "ok"
    bad = c.post("/api/search", json={"appliances": [{"name": "X", "kw": 0, "allowed": ["Noon"]}]})
    assert bad.status_code == 400

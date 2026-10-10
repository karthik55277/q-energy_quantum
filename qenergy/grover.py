"""Grover's search with Qiskit.

The circuit, in four ideas:
  1. Hadamard on every qubit  -> all plans equally likely (superposition)
  2. Oracle                   -> flips the sign of every good plan
  3. Diffuser                 -> reflects all amplitudes about their average,
                                 so the flipped (good) plans grow
  4. Repeat 2-3 about k = π/4·√(N/M) times, then measure
"""
from __future__ import annotations

import math

from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import ZGate
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

from qenergy import household as hh


# ---------------------------------------------------------------- building blocks
def flip_all_ones(qc: QuantumCircuit, n: int) -> None:
    """Multi-controlled Z: changes the sign of |11...1> and nothing else."""
    if n == 1:
        qc.z(0)
    else:
        qc.append(ZGate().control(n - 1, annotated=False), range(n))


def oracle(n: int, good: list[str]) -> QuantumCircuit:
    """Flip the sign of each good plan.

    For a plan like 01010011: put X on every qubit that should be 0, so the plan
    becomes 11111111; flip its sign; undo the X gates.
    Qiskit numbers qubits from the right, so string position p is qubit n-1-p.
    """
    qc = QuantumCircuit(n, name="Oracle")
    for plan in good:
        zeros = [q for q in range(n) if plan[n - 1 - q] == "0"]
        if zeros:
            qc.x(zeros)
        flip_all_ones(qc, n)
        if zeros:
            qc.x(zeros)
    return qc


def diffuser(n: int) -> QuantumCircuit:
    """Reflection about the average amplitude (2|s><s| - I):  H X (flip |1..1>) X H.

    Those gates give -(2|s><s| - I). The overall minus sign (a "global phase")
    never changes a measurement, but we set it so the amplitudes we draw match
    the textbook exactly: good plans stay positive after each round.
    """
    qc = QuantumCircuit(n, name="Diffuser", global_phase=math.pi)
    qc.h(range(n))
    qc.x(range(n))
    flip_all_ones(qc, n)
    qc.x(range(n))
    qc.h(range(n))
    return qc


def best_rounds(n_plans: int, n_good: int) -> int:
    """k = floor(π / (4θ)) with sin θ = √(M/N): the round count that peaks P(good)."""
    if n_good == 0 or n_good >= n_plans:
        return 0
    theta = math.asin(math.sqrt(n_good / n_plans))
    return math.floor(math.pi / (4 * theta))


def grover_circuit(n: int, good: list[str], rounds: int) -> QuantumCircuit:
    o = oracle(n, good).to_gate(label="Oracle")
    d = diffuser(n).to_gate(label="Diffuser")
    qc = QuantumCircuit(n, n)
    qc.h(range(n))
    for _ in range(rounds):
        qc.append(o, range(n))
        qc.append(d, range(n))
    qc.measure(range(n), range(n))
    return qc


# ---------------------------------------------------------------- the full search
def search(appliances: list[dict], max_bill: float, max_peak: float,
           shots: int = 1000, seed: int | None = None) -> dict:
    """Run Grover's search for a good plan and return everything the UI shows."""
    hh.check_appliances(appliances)
    n = hh.n_qubits(appliances)
    N = 2 ** n
    good = hh.good_plans(appliances, max_bill, max_peak)          # classical rule-check
    M = len(good)
    if M == 0:
        return {"status": "none", "n_qubits": n, "n_plans": N, "n_good": 0,
                "message": "No plan meets both limits. Raise the bill or power limit a little."}

    k = best_rounds(N, M)

    # 1) Watch the amplitudes round by round (exact state vector from Qiskit).
    frames = []
    start = QuantumCircuit(n)
    start.h(range(n))
    state = Statevector(start)
    frames.append({"label": "start", "round": 0, "amps": _real(state)})
    o, d = oracle(n, good), diffuser(n)
    for r in range(1, k + 1):
        state = state.evolve(o)
        frames.append({"label": "oracle", "round": r, "amps": _real(state)})
        state = state.evolve(d)
        frames.append({"label": "diffuser", "round": r, "amps": _real(state)})

    # 2) Run the real circuit on the Aer simulator and measure.
    qc = grover_circuit(n, good, k)
    sim = AerSimulator(seed_simulator=seed)
    result = sim.run(transpile(qc, sim, seed_transpiler=seed), shots=shots, memory=True).result()
    counts = result.get_counts()
    picked = result.get_memory()[0]                                 # the first measurement
    hits = sum(c for b, c in counts.items() if b in set(good))

    plan = hh.decode(picked)
    usual = [a.get("usual", a["allowed"][0]) for a in appliances]
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
    return {
        "status": "ok",
        "n_qubits": n, "n_plans": N, "n_good": M, "rounds": k,
        "good": good,
        "frames": frames,
        "shots": shots,
        "success_rate": hits / shots,
        "theory_success": math.sin((2 * k + 1) * math.asin(math.sqrt(M / N))) ** 2,
        "random_guess": M / N,
        "picked": picked,
        "picked_is_good": picked in good,
        "plan": plan,
        "plan_score": hh.score(plan, appliances),
        "usual": usual,
        "usual_score": hh.score(usual, appliances),
        "top_counts": [{"bitstring": b, "count": c, "good": b in good} for b, c in top],
        "circuit": str(grover_circuit(n, good, 1).draw(output="text", fold=120)),
        "engine": "Qiskit Aer",
    }


def _real(state: Statevector) -> list[float]:
    # Grover keeps every amplitude real, so the real part is the whole story.
    return [round(float(a.real), 6) for a in state.data]

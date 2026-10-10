# How Q-Energy works

## 1. The problem in one paragraph

A home has 4 appliances. Each must run once a day for one hour, in one of 4 time slots: Morning, Noon, Evening or Night. Electricity costs a different amount in each slot, and rooftop solar is strongest at noon. If heavy appliances run together the house draws too much power at once, which can trip the main switch and strains the grid. We want a plan where:

* each appliance runs at a time the family accepts,
* the daily bill is at most a limit (default ₹45),
* the power used at the same time is at most a limit (default 4 kW).

| Appliance | Power | Allowed times |
|---|---|---|
| Washing machine | 0.8 kW | Morning, Noon, Evening |
| Dishwasher | 1.2 kW | Noon, Evening, Night |
| Water heater | 2.0 kW | Morning, Noon, Night |
| EV charger | 3.5 kW | Evening, Night |

| Slot | Price | Solar | Grid CO₂ |
|---|---|---|---|
| Morning | ₹6/kWh | 0.5 kW | 0.75 kg/kWh |
| Noon | ₹4/kWh | 4.0 kW | 0.30 kg/kWh |
| Evening | ₹10/kWh | 0.5 kW | 0.85 kg/kWh |
| Night | ₹7/kWh | 0 kW | 0.55 kg/kWh |

## 2. Plans as qubits

Each appliance needs one of 4 slots, and 4 choices fit in 2 bits:

| Bits | Slot |
|---|---|
| 00 | Morning |
| 01 | Noon |
| 10 | Evening |
| 11 | Night |

Four appliances × 2 bits = **8 qubits**. 8 qubits can be in **2⁸ = 256** states at once, so every possible daily plan is one state.

Example: `01 01 00 11` = Washing machine Noon, Dishwasher Noon, Water heater Morning, EV charger Night.

## 3. Scoring a plan (classical maths, `qenergy/household.py`)

* **Load in a slot** = sum of the power of appliances running in it.
* **Peak** = the highest slot load.
* **Bill** = Σ (slot load × slot price).
* **CO₂** = Σ (slot load × grid carbon intensity).
* **Solar share** = Σ min(slot load, solar available) ÷ total energy.

Worked example for `01 01 00 11`: Morning load 2.0 kW, Noon 2.0, Evening 0, Night 3.5. Bill = 2×6 + 2×4 + 3.5×7 = ₹44.5. Peak = 3.5 kW. This is a good plan.

## 4. Grover's search (quantum, `qenergy/grover.py`)

**Step A: superposition.** Put a Hadamard gate (H) on all 8 qubits. Now all 256 plans have the same amplitude, 1/16, so each has a 1/256 chance of being measured.

**Step B: oracle.** The oracle flips the sign of every good plan's amplitude (+ becomes −). In the app these are the dots that flash red. For each good plan:
* put X gates on the qubits that should be 0, which turns that plan into |11111111⟩,
* apply a multi-controlled Z, which flips the sign of |11111111⟩ only,
* undo the X gates.

**Step C: diffuser.** Reflect every amplitude about the average (new = 2 × average − old). Good plans have negative amplitudes, far below the average, so they bounce up high; the rest shrink a little. In gates: H, X, multi-controlled Z, X, H.

**Step D: repeat, then measure.** Do B and C k times, with

> k ≈ (π / 4) × √(N / M)  (N = 256 plans, M = good plans)

With M = 3, k = 7. The chance of measuring a good plan grows each round:

| Round | Chance of a good plan |
|---|---|
| 0 | 1.2% |
| 1 | 10.2% |
| 2 | 26.6% |
| 3 | 47.4% |
| 4 | 68.6% |
| 5 | 86.4% |
| 6 | 97.4% |
| 7 | **99.7%** |

Doing more rounds than k is worse: the chance goes back down.

**Step E: measure and decode.** Qiskit Aer runs the circuit 1,000 times ("shots"). The first result is our plan. We decode its bits back into times and score it.

## 5. Why use Grover?

| Method | Tries to find a good plan (on average) |
|---|---|
| Guess plans one by one | about N / M = 256 / 3 ≈ 85 |
| Grover | about √(N / M) ≈ 7 rounds |

This is a **quadratic speed-up** in the number of times the rules are checked. It matters more as homes get bigger: with 8 appliances there are 65,536 plans.

## 6. Being honest about the limits

* **Hybrid design.** The oracle must know which plans are good. Here an ordinary computer checks the rules and the oracle is built from that list. A fully quantum oracle would compute the bill on extra qubits using quantum arithmetic, which is much bigger.
* **Simulator, not hardware.** A laptop simulating qubits is slower than simply checking 256 plans. The project shows *how* Grover works on a real problem, not a speed record.
* **Grover finds *a* good plan, not always the cheapest.** To get the cheapest, lower the bill limit until only one plan is left (try ₹41 in the app).
* **Noise.** On today's real quantum chips, an 8-qubit multi-controlled gate breaks down into many 2-qubit gates, and their errors add up.

## 7. Questions you may be asked

**Q: Where is the superposition?** The H gates on all 8 qubits. After them, all 256 plans exist together with equal amplitude.

**Q: What does the oracle do?** It flips the sign of the good plans' amplitudes. That alone doesn't change any probability (a negative amplitude squared is still positive); it only tags them.

**Q: What does the diffuser do?** It reflects all amplitudes about their average. Tagged amplitudes are below the average, so they end up far above it. This is called amplitude amplification.

**Q: Why 7 rounds?** k = ⌊π / (4θ)⌋ with sin θ = √(M/N) = √(3/256), which gives 7. Each round turns the state by 2θ towards the good plans; 7 rounds bring it closest to 90°.

**Q: What if there are no good plans?** The app says so and asks you to relax a limit. Grover can't amplify nothing.

**Q: Is the measurement always right?** No, about 99.7% of the time. If a bad plan comes out, press "Search again".

**Q: Where are the tests?** `tests/test_qenergy.py` (18 checks). They cover the bill maths, the encoding, the fact that the oracle flips exactly the good plans, the diffuser reflecting about the mean, the round count, the measured success rate, and the web API.

"""The household: appliances, time slots, and how a plan is scored.

Everything here is ordinary (classical) Python. The quantum part is in grover.py.
"""
from __future__ import annotations

# Four time slots. Each slot gets a 2-bit code: 00, 01, 10, 11.
SLOTS = [
    {"name": "Morning", "price": 6.0,  "solar": 0.5, "co2": 0.75},   # ₹/kWh, solar kW, kg CO2 per kWh
    {"name": "Noon",    "price": 4.0,  "solar": 4.0, "co2": 0.30},
    {"name": "Evening", "price": 10.0, "solar": 0.5, "co2": 0.85},
    {"name": "Night",   "price": 7.0,  "solar": 0.0, "co2": 0.55},
]
SLOT_NAMES = [s["name"] for s in SLOTS]

# Four appliances. Each runs once a day for one hour.
# "allowed" = slots the family is happy with; "usual" = when they run it today.
APPLIANCES = [
    {"name": "Washing machine", "kw": 0.8, "allowed": ["Morning", "Noon", "Evening"], "usual": "Evening"},
    {"name": "Dishwasher",      "kw": 1.2, "allowed": ["Noon", "Evening", "Night"],   "usual": "Evening"},
    {"name": "Water heater",    "kw": 2.0, "allowed": ["Morning", "Noon", "Night"],   "usual": "Morning"},
    {"name": "EV charger",      "kw": 3.5, "allowed": ["Evening", "Night"],           "usual": "Evening"},
]

BITS_PER_APPLIANCE = 2


def n_qubits(appliances: list[dict]) -> int:
    return BITS_PER_APPLIANCE * len(appliances)


def decode(bitstring: str) -> list[str]:
    """'01 01 00 11' or '01010011' -> ['Noon', 'Noon', 'Morning', 'Night'].

    Read left to right: the first two bits are appliance 1, the next two appliance 2, ...
    """
    b = bitstring.replace(" ", "")
    if len(b) % 2 or set(b) - {"0", "1"}:
        raise ValueError(f"Not a valid plan bitstring: {bitstring!r}")
    return [SLOT_NAMES[int(b[i:i + 2], 2)] for i in range(0, len(b), 2)]


def encode(plan: list[str]) -> str:
    return "".join(format(SLOT_NAMES.index(s), "02b") for s in plan)


def pretty(bitstring: str) -> str:
    return " ".join(bitstring[i:i + 2] for i in range(0, len(bitstring), 2))


def score(plan: list[str], appliances: list[dict]) -> dict:
    """Bill, peak power, CO2 and solar share for one daily plan."""
    load = {s: 0.0 for s in SLOT_NAMES}
    for app, slot in zip(appliances, plan):
        load[slot] += app["kw"]                       # 1 hour, so kW = kWh
    bill = sum(load[s["name"]] * s["price"] for s in SLOTS)
    co2 = sum(load[s["name"]] * s["co2"] for s in SLOTS)
    solar = sum(min(load[s["name"]], s["solar"]) for s in SLOTS)
    total = sum(load.values())
    return {
        "load": [round(load[s], 3) for s in SLOT_NAMES],
        "bill": round(bill, 2),
        "peak": round(max(load.values()), 3),
        "co2": round(co2, 3),
        "solar_share": round(solar / total, 4) if total else 0.0,
    }


def is_allowed(plan: list[str], appliances: list[dict]) -> bool:
    return all(slot in app["allowed"] for app, slot in zip(appliances, plan))


def is_good(plan: list[str], appliances: list[dict], max_bill: float, max_peak: float) -> bool:
    if not is_allowed(plan, appliances):
        return False
    s = score(plan, appliances)
    return s["bill"] <= max_bill + 1e-9 and s["peak"] <= max_peak + 1e-9


def good_plans(appliances: list[dict], max_bill: float, max_peak: float) -> list[str]:
    """Every bitstring whose plan is allowed and within both limits.

    This is the rule-check the oracle uses (the classical half of the hybrid design).
    """
    n = n_qubits(appliances)
    out = []
    for x in range(2 ** n):
        b = format(x, f"0{n}b")
        if is_good(decode(b), appliances, max_bill, max_peak):
            out.append(b)
    return out


def check_appliances(appliances: list[dict]) -> None:
    """Raise ValueError with a plain message if the input can't be used."""
    if not 1 <= len(appliances) <= 6:
        raise ValueError("Use between 1 and 6 appliances.")
    for a in appliances:
        if not a.get("name"):
            raise ValueError("Every appliance needs a name.")
        if not isinstance(a.get("kw"), (int, float)) or not 0 < a["kw"] <= 20:
            raise ValueError(f"{a['name']}: power must be between 0 and 20 kW.")
        if not a.get("allowed"):
            raise ValueError(f"{a['name']}: allow at least one time slot.")
        bad = [s for s in a["allowed"] if s not in SLOT_NAMES]
        if bad:
            raise ValueError(f"{a['name']}: unknown time slot {bad}.")

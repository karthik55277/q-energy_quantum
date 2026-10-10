// Q-Energy page logic.
// The quantum search runs in Python with Qiskit (POST /api/search).
// If the page is opened without the Python app running, it falls back to an
// exact in-browser simulation of the same circuit, and says so.
(() => {
  // ---------- defaults (replaced by /api/household when the app is running) ----------
  let SLOTS = [
    { name: "Morning", price: 6, solar: 0.5, co2: 0.75 },
    { name: "Noon", price: 4, solar: 4.0, co2: 0.30 },
    { name: "Evening", price: 10, solar: 0.5, co2: 0.85 },
    { name: "Night", price: 7, solar: 0.0, co2: 0.55 },
  ];
  let DEFAULT = [
    { name: "Washing machine", kw: 0.8, allowed: ["Morning", "Noon", "Evening"], usual: "Evening" },
    { name: "Dishwasher", kw: 1.2, allowed: ["Noon", "Evening", "Night"], usual: "Evening" },
    { name: "Water heater", kw: 2.0, allowed: ["Morning", "Noon", "Night"], usual: "Morning" },
    { name: "EV charger", kw: 3.5, allowed: ["Evening", "Night"], usual: "Evening" },
  ];
  const ICONS = {
    "Washing machine": '<svg viewBox="0 0 44 44" fill="none" stroke="currentColor" stroke-width="2"><rect x="7" y="5" width="30" height="34" rx="4"/><circle cx="22" cy="24" r="9"/><circle cx="22" cy="24" r="4" fill="currentColor" stroke="none" opacity=".25"/><line x1="12" y1="10" x2="17" y2="10"/></svg>',
    "Dishwasher": '<svg viewBox="0 0 44 44" fill="none" stroke="currentColor" stroke-width="2"><rect x="7" y="5" width="30" height="34" rx="4"/><line x1="7" y1="13" x2="37" y2="13"/><line x1="13" y1="21" x2="31" y2="21"/><line x1="13" y1="27" x2="31" y2="27"/><line x1="13" y1="33" x2="31" y2="33"/></svg>',
    "Water heater": '<svg viewBox="0 0 44 44" fill="none" stroke="currentColor" stroke-width="2"><rect x="11" y="4" width="22" height="36" rx="10"/><path d="M22 14c-3 4-4 6-4 8a4 4 0 0 0 8 0c0-2-1-4-4-8z" fill="currentColor" stroke="none" opacity=".35"/></svg>',
    "EV charger": '<svg viewBox="0 0 44 44" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 28l3-9a4 4 0 0 1 4-3h18a4 4 0 0 1 4 3l3 9v6H6z"/><circle cx="13" cy="34" r="3"/><circle cx="31" cy="34" r="3"/><path d="M23 6l-4 7h6l-4 7" stroke-linejoin="round"/></svg>',
    other: '<svg viewBox="0 0 44 44" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6v10M26 6v10M13 16h18v6a9 9 0 0 1-18 0zM22 31v8"/></svg>',
  };

  const N = 256;
  const $ = id => document.getElementById(id);
  const inr = v => "₹" + (Math.round(v * 10) / 10).toLocaleString("en-IN");
  const clone = list => list.map(a => ({ ...a, allowed: [...a.allowed] }));
  let apps = clone(DEFAULT);
  const slotNames = () => SLOTS.map(s => s.name);

  // ---------- energy model (same rules as qenergy/household.py) ----------
  const bits = x => x.toString(2).padStart(8, "0");
  const pretty = b => b.match(/../g).join(" ");
  const decode = b => b.match(/../g).map(c => SLOTS[parseInt(c, 2)].name);
  function score(plan) {
    const load = Object.fromEntries(SLOTS.map(s => [s.name, 0]));
    plan.forEach((slot, i) => { load[slot] += apps[i].kw; });
    const bill = SLOTS.reduce((t, s) => t + load[s.name] * s.price, 0);
    const co2 = SLOTS.reduce((t, s) => t + load[s.name] * s.co2, 0);
    const solar = SLOTS.reduce((t, s) => t + Math.min(load[s.name], s.solar), 0);
    const total = Object.values(load).reduce((a, b) => a + b, 0);
    return { bill, co2, peak: Math.max(...Object.values(load)), solar_share: total ? solar / total : 0 };
  }
  function goodPlans() {
    const bill = +$("bill").value, peak = +$("peak").value, out = [];
    for (let x = 0; x < N; x++) {
      const b = bits(x), plan = decode(b);
      if (!plan.every((s, i) => apps[i].allowed.includes(s))) continue;
      const m = score(plan);
      if (m.bill <= bill + 1e-9 && m.peak <= peak + 1e-9) out.push(b);
    }
    return out;
  }

  // ---------- navigation ----------
  function show(n) {
    [1, 2, 3, 4].forEach(i => { $("s" + i).hidden = i !== n; });
    [...$("rail").children].forEach((li, i) => { li.className = i + 1 < n ? "done" : i + 1 === n ? "now" : ""; });
    if (n === 2) refreshLimits();
    if (n === 3) resetSearch();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---------- step 1 ----------
  function drawApps() {
    $("apps").innerHTML = apps.map((a, i) => `
      <div class="app">
        <div style="color:var(--quantum)">${ICONS[a.name] || ICONS.other}</div>
        <div>
          <div class="name">${a.name} <span class="kw">${a.kw} kW</span></div>
          <div class="times">${SLOTS.map(s =>
            `<button type="button" class="time ${a.allowed.includes(s.name) ? "on" : ""}" data-a="${i}" data-s="${s.name}" aria-pressed="${a.allowed.includes(s.name)}">${s.name}</button>`).join("")}
          </div>
        </div>
      </div>`).join("");
    const fits = apps.reduce((p, a) => p * a.allowed.length, 1);
    $("count1").innerHTML = `<b>${fits}</b> of the 256 possible day plans fit these times. The quantum search looks at all 256 at once.`;
  }
  $("apps").addEventListener("click", e => {
    const b = e.target.closest(".time"); if (!b) return;
    const a = apps[+b.dataset.a], s = b.dataset.s;
    if (a.allowed.includes(s)) { if (a.allowed.length > 1) a.allowed = a.allowed.filter(v => v !== s); }
    else a.allowed = slotNames().filter(n => n === s || a.allowed.includes(n));
    drawApps();
  });

  // ---------- step 2 ----------
  function refreshLimits() {
    $("billOut").textContent = "₹" + $("bill").value;
    $("peakOut").textContent = (+$("peak").value).toFixed(1) + " kW";
    const g = goodPlans().length, v = $("verdict");
    if (g === 0) {
      v.className = "verdict none";
      v.textContent = "No plan meets both limits. Raise the bill limit or the power limit a little.";
    } else {
      v.className = "verdict ok";
      v.innerHTML = `<b>${g}</b> of 256 plans are good. Guessing at random would find one only ${(g / N * 100).toFixed(1)}% of the time.`;
    }
    $("to3").disabled = g === 0;
  }
  $("bill").addEventListener("input", refreshLimits);
  $("peak").addEventListener("input", refreshLimits);

  // ---------- step 3: the search ----------
  const dots = [];
  for (let x = 0; x < N; x++) {
    const d = document.createElement("div");
    d.className = "dot";
    $("grid").appendChild(d);
    dots.push(d);
  }
  let good = new Set(), result = null, running = false;

  function paint(amps, opts = {}) {
    let maxP = 0;
    for (let x = 0; x < N; x++) maxP = Math.max(maxP, amps[x] * amps[x]);
    let pg = 0;
    for (let x = 0; x < N; x++) {
      const b = bits(x), p = amps[x] * amps[x], r = Math.sqrt(p / maxP), d = dots[x];
      if (good.has(b)) pg += p;
      d.style.setProperty("--s", (0.3 + 0.7 * r).toFixed(3));
      d.style.backgroundColor = `color-mix(in srgb, var(--quantum) ${Math.round(r * 100)}%, var(--dot))`;
      d.classList.toggle("neg", !!opts.neg && amps[x] < 0);
      d.classList.toggle("good", good.has(b));
      d.classList.toggle("picked", b === opts.picked);
      d.title = `${pretty(b)} · ${decode(b).join(", ")}`;
    }
    $("prob").textContent = (pg * 100).toFixed(1) + "%";
    $("meter").style.width = (pg * 100).toFixed(1) + "%";
  }
  function resetSearch() {
    good = new Set(goodPlans());
    result = null;
    const M = good.size, k = rounds(M);
    $("guess").textContent = `Random guess: ${(M / N * 100).toFixed(1)}%`;
    $("phase").textContent = `${M} good plans hidden among 256. Grover needs about ${k} rounds.`;
    $("run").textContent = "Start quantum search";
    $("run").disabled = false;
    $("to4").disabled = true;
    $("shots").textContent = "";
    $("err").hidden = true;
    paint(new Array(N).fill(1 / 16));
  }
  function rounds(M) {
    if (M === 0 || M >= N) return 0;
    return Math.floor(Math.PI / (4 * Math.asin(Math.sqrt(M / N))));
  }
  const wait = ms => new Promise(r => setTimeout(r, matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : ms));

  async function getResult() {
    const body = { appliances: apps, max_bill: +$("bill").value, max_peak: +$("peak").value };
    try {
      const res = await fetch("api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok) throw Object.assign(new Error(data.message || "The search failed."), { fromServer: true });
      setEngine(true);
      return data;
    } catch (e) {
      if (e.fromServer) throw e;
      setEngine(false);
      return browserSearch();
    }
  }
  function setEngine(qiskit) {
    $("engine").className = "engine" + (qiskit ? "" : " local");
    $("engine").textContent = qiskit ? "Running on Qiskit Aer" : "Browser simulation (start app.py for Qiskit)";
  }

  // Exact state-vector simulation, used only when the Python app isn't running.
  function browserSearch() {
    const goodList = [...good], M = goodList.length, k = rounds(M);
    const idx = goodList.map(b => parseInt(b, 2));
    let psi = new Array(N).fill(1 / Math.sqrt(N));
    const frames = [{ label: "start", round: 0, amps: [...psi] }];
    for (let r = 1; r <= k; r++) {
      idx.forEach(i => { psi[i] = -psi[i]; });
      frames.push({ label: "oracle", round: r, amps: [...psi] });
      const mean = psi.reduce((a, b) => a + b, 0) / N;
      psi = psi.map(a => 2 * mean - a);
      frames.push({ label: "diffuser", round: r, amps: [...psi] });
    }
    const shots = 1000, counts = new Map();
    let first = null;
    for (let s = 0; s < shots; s++) {
      let u = Math.random(), acc = 0, pick = N - 1;
      for (let x = 0; x < N; x++) { acc += psi[x] * psi[x]; if (u <= acc) { pick = x; break; } }
      const b = bits(pick);
      if (first === null) first = b;                     // the first measurement is "the" answer
      counts.set(b, (counts.get(b) || 0) + 1);
    }
    const hits = goodList.reduce((t, b) => t + (counts.get(b) || 0), 0);
    const plan = decode(first), usual = apps.map(a => a.usual || a.allowed[0]);
    return {
      status: "ok", n_good: M, rounds: k, frames, shots, success_rate: hits / shots,
      random_guess: M / N, picked: first, picked_is_good: good.has(first),
      plan, plan_score: score(plan), usual, usual_score: score(usual), circuit: null, engine: "browser",
    };
  }

  async function runSearch() {
    if (running) return;
    running = true;
    $("run").disabled = true;
    $("to4").disabled = true;
    $("err").hidden = true;
    $("shots").textContent = "";
    $("phase").textContent = "Building the circuit…";
    let r;
    try { r = await getResult(); }
    catch (e) {
      $("err").textContent = e.message; $("err").hidden = false;
      $("run").disabled = false; running = false; return;
    }
    if (r.status !== "ok") {
      $("err").textContent = r.message; $("err").hidden = false;
      $("run").disabled = false; running = false; return;
    }
    good = new Set(r.good || [...good]);
    const k = r.rounds;
    for (const f of r.frames) {
      if (f.label === "start") $("phase").textContent = "All 256 plans start equally likely (superposition).";
      if (f.label === "oracle") $("phase").innerHTML = `<b>Round ${f.round} of ${k}.</b> The oracle marks the good plans (red).`;
      if (f.label === "diffuser") $("phase").innerHTML = `<b>Round ${f.round} of ${k}.</b> The diffuser boosts the marked plans.`;
      paint(f.amps, { neg: f.label === "oracle" });
      await wait(f.label === "start" ? 900 : 700);
    }
    const last = r.frames[r.frames.length - 1].amps;
    paint(last, { picked: r.picked });
    $("phase").innerHTML = r.picked_is_good
      ? `<b>Measured:</b> <span class="mono">${pretty(r.picked)}</span>, a good plan.`
      : `<b>Measured:</b> <span class="mono">${pretty(r.picked)}</span>. Unlucky, this one isn't good (it happens a few % of the time). Search again.`;
    $("shots").textContent = `The circuit was run ${r.shots.toLocaleString()} times: a good plan came out ${Math.round(r.success_rate * r.shots).toLocaleString()} times (${(r.success_rate * 100).toFixed(1)}%).`;
    if (r.circuit) $("circuit").textContent = r.circuit;
    result = r;
    $("run").textContent = "Search again";
    $("run").disabled = false;
    $("to4").disabled = !r.picked_is_good;
    running = false;
  }
  $("run").addEventListener("click", runSearch);

  // ---------- step 4 ----------
  function showPlan() {
    const r = result, m = r.plan_score, u = r.usual_score;
    $("planLead").innerHTML = `The quantum search picked plan <span class="mono">${pretty(r.picked)}</span>. Here is what it means:`;
    $("plan").innerHTML = apps.map((a, i) => {
      const s = SLOTS.find(x => x.name === r.plan[i]);
      return `<div class="row"><span>${a.name}</span><b><span class="${s.solar >= 2 ? "sun" : ""}">${s.name}</span></b></div>`;
    }).join("");
    const td = (v, better) => `<td class="${better ? "win" : ""}">${v}</td>`;
    $("compare").innerHTML = `
      <tr><th></th><th>Quantum plan</th><th>Usual routine*</th></tr>
      <tr><td>Daily bill</td>${td(inr(m.bill), m.bill < u.bill)}<td>${inr(u.bill)}</td></tr>
      <tr><td>Highest power at once</td>${td(m.peak.toFixed(1) + " kW", m.peak < u.peak)}<td>${u.peak.toFixed(1)} kW</td></tr>
      <tr><td>CO₂ per day</td>${td(m.co2.toFixed(2) + " kg", m.co2 < u.co2)}<td>${u.co2.toFixed(2)} kg</td></tr>
      <tr><td>Powered by solar</td>${td(Math.round(m.solar_share * 100) + "%", m.solar_share > u.solar_share)}<td>${Math.round(u.solar_share * 100)}%</td></tr>`;
    const month = (u.bill - m.bill) * 30, year = (u.co2 - m.co2) * 365;
    const usualText = apps.map((a, i) => `${a.name} at ${r.usual[i].toLowerCase()}`).join(", ");
    $("saving").innerHTML = (month > 0
      ? `You would save about <b>${inr(month)} a month</b> and <b>${Math.round(year)} kg of CO₂ a year</b>.`
      : `This plan costs about the same as the usual routine.`)
      + `<br><small style="color:var(--muted)">*Usual routine: ${usualText}.</small>`;
    $("facts").innerHTML = `
      <div class="fact"><b>${r.rounds}</b><span>Grover rounds used</span></div>
      <div class="fact"><b>~${Math.round(N / r.n_good)}</b><span>random tries needed on average without quantum</span></div>
      <div class="fact"><b>${(r.success_rate * 100).toFixed(1)}%</b><span>of ${r.shots.toLocaleString()} runs gave a good plan</span></div>`;
    show(4);
  }

  // ---------- wiring ----------
  $("to2").addEventListener("click", () => show(2));
  $("back1").addEventListener("click", () => show(1));
  $("to3").addEventListener("click", () => show(3));
  $("back2").addEventListener("click", () => show(2));
  $("to4").addEventListener("click", showPlan);
  $("again").addEventListener("click", () => show(3));
  $("restart").addEventListener("click", () => {
    apps = clone(DEFAULT);
    $("bill").value = 45; $("peak").value = 4;
    drawApps(); show(1);
  });

  // ---------- start ----------
  async function boot() {
    try {
      const res = await fetch("api/household");
      if (res.ok) {
        const h = await res.json();
        SLOTS = h.slots; DEFAULT = h.appliances; apps = clone(DEFAULT);
        setEngine(true);
      } else setEngine(false);
    } catch { setEngine(false); }
    drawApps();
    show(1);
  }
  boot();
})();

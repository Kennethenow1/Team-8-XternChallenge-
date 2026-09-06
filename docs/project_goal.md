# Project goal — MISO interconnection policy-response simulator

## Purpose

The goal is not primarily to tell a MISO planner *why* a project is risky. The larger goal is to use predicted withdrawals as an input into an **actionable response system**:

```text
Predicted withdrawals  →  Expected consequences  →  MISO response
```

and then:

```text
Can MISO modify that response to reduce the consequences?
```

Think of the end product as a **policy-response simulator**: given expected or actual withdrawals in a study group, reconstruct what MISO must do under current rules, estimate downstream cost / delay / restudy / secondary-withdrawal burden, and ask which *feasible* response alternative best reduces that burden.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Features → P(W)                    Phase 1 — prediction                │
│       ↓                                                                 │
│  Withdrawal scenarios → consequences   Phase 2 — impact                 │
│       ↓                                                                 │
│  Response alternatives → a*            Phase 2 — policy optimization    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 — Withdrawal prediction

Predict, for each project \(i\) on observation date \(t\):

\[
P\bigl(\text{withdraw in the next 12 months} \mid \text{information available at } t\bigr)
\]

**Deliverables to Phase 2** (not a full causal “why” report):

| Output | Role |
|--------|------|
| Project identity | Who is at risk |
| Withdrawal probability | Scenario weights |
| Capacity (MW) | Size of the shock |
| Study / POI / group context | Which process pathway is affected |

The model-ready feature matrix (~97 features) stays oriented to **withdrawal prediction**. Do **not** distort Phase 1 features to encode Phase 2 actions. Prefer a full-feature / interpretable model for the main predictor; do **not** PCA the main withdrawal model unless validation shows a clear advantage.

This repository’s current product is the **point-in-time feature store** that supports Phase 1. Model training may live elsewhere; the database must still emit PIT-safe inputs suitable for the chain above.

---

## Phase 2 — Response to predicted / actual withdrawals

### Research question

> Given predicted withdrawals and their expected effects on the remaining interconnection queue, how can MISO modify its existing response procedures to minimize downstream cost, delay, repeated studies, and secondary withdrawals while satisfying reliability and regulatory requirements?

Call these interventions **response policies** or **post-risk interventions** — not generic “policies that prevent withdrawal.”

### Worked example

Suppose Phase 1 predicts, for one study group:

| Project | MW | 12-mo withdrawal probability |
|---------|-----|------------------------------|
| A | 500 | 82% |
| B | 300 | 67% |
| C | 400 | 21% |
| D | 200 | 14% |

Stopping at “A and B are high risk” is insufficient. Phase 2 reconstructs the **existing** MISO pathway if A/B withdraw:

```text
A, B withdraw
    ↓
Affected-project / system impact determination
    ↓
Restudy / network analysis if required
    ↓
Upgrade requirements / costs change
    ↓
Remaining projects make new decisions
    ↓
Possibly: C withdraws → additional process churn
```

Predictions then have **operational meaning**: expected MW lost, restudy likelihood, cost/delay shock to remaining projects, and secondary-withdrawal risk.

### Scenario planning (before the event)

With \(P(A)=0.85\), \(P(B)=0.72\), \(P(C)=0.15\), evaluate consequences under current rules for:

- Scenario 0 — nobody withdraws  
- Scenario 1 — A withdraws  
- Scenario 2 — B withdraws  
- Scenario 3 — A and B withdraw  

Probabilities can weight scenarios. Independence (\(P(A\cap B)\approx 0.85\times 0.72\)) is only illustrative; projects in the same study group are likely **dependent**. The point is to plan response burden *before* “A withdrew — now what?”

---

## Optimization objective

For each feasible response \(a\), estimate:

\[
J(a) = w_1 C(a) + w_2 D(a) + w_3 R(a) + w_4 W(a) + w_5 S(a)
\]

| Term | Meaning |
|------|---------|
| \(C\) | Additional cost / cost shock |
| \(D\) | Additional delay |
| \(R\) | Number / burden of restudies |
| \(W\) | Expected secondary withdrawals (count or MW) |
| \(S\) | Stranded or unnecessary system work |

Then:

\[
a^* = \arg\min_a J(a)
\]

subject to **reliability**, **tariff / FERC**, **engineering**, and **fairness** constraints.

The optimizer must only choose among **legally and technically feasible** alternatives. It cannot recommend “skip the restudy because it is expensive” if the tariff requires one.

---

## Phase 2 data (separate from the Phase 1 matrix)

Do not bend the 97-feature withdrawal matrix into a policy simulator. Build an additional **action / process** dataset.

### Historical episode table (illustrative grain)

| Withdrawal event | Situation before | MISO action | Steps | Time | Cost effect | Remaining-project effect | Next withdrawal? |
|------------------|------------------|-------------|-------|------|-------------|--------------------------|------------------|
| W1 | 1 project leaves DPP | Restudy | 4 | 90d | +$X | B cost ↑ | Yes |
| W2 | 3 projects leave group | … | … | … | … | … | … |

### Rules / policy table

| Trigger | Current MISO requirement | Action | Exception | Effective dates | Authority |
|---------|--------------------------|--------|-----------|-----------------|-----------|
| Withdrawal at stage X | … | … | … | … | Tariff / BPM |
| Material study impact | … | Restudy | … | … | Tariff / BPM |
| Cost shift | … | … | … | … | Tariff / BPM |

Together these support three comparisons:

1. **What MISO says should happen** (rules)  
2. **What historically happened** (episodes)  
3. **What could happen under a modified response** (counterfactual / simulator)

---

## Prevention as a downstream benefit

The initial optimization objective is **not** “prevent withdrawals.”

Optimize the **response** to expected or actual withdrawals. Prevention may emerge:

```text
Current response → restudy → cost shock → delay → secondary withdrawal
Modified response → less repeated work → smaller uncertainty/delay → lower secondary-withdrawal probability
```

So withdrawal prevention is a **possible benefit** of better response policy, not an assumption from the start. That is a stronger research design: not every withdrawal is assumed bad or preventable.

---

## Implications for modeling practice

| Choice | Guidance |
|--------|----------|
| Phase 1 features | Keep prediction-oriented; do not encode Phase 2 actions into \(X\) |
| PCA on main model | Avoid unless validated advantage; Phase 2 needs project-level \(P(W)\), MW, study context |
| Phase 2 tables | New episode + rules datasets; not a reshape of `model_ready_train` |
| Success for Phase 1 | Reliable, PIT-safe probabilities usable as scenario inputs |
| Success for Phase 2 | Feasible \(a^*\) that reduces \(J(a)\) under constraints |

---

## Repo mapping (current)

| Piece | Location / status |
|-------|-------------------|
| PIT feature store (Phase 1 inputs) | `data/gold/withdrawal_panel_enriched.*`, `data/gold/modeling/` |
| Model-ready matrix | ~97 features — withdrawal prediction only |
| Phase 2 episode / rules tables | Not built yet — future work |
| Response optimizer | Not built yet — future work |

See also: [pipeline.md](pipeline.md), [data_catalog.md](data_catalog.md), [README](../README.md).

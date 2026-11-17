# Pilot analysis plan (pre-registered style)

**Primary outcome:** delayed (24–72h) accuracy on unseen Form C items for the focus skill.

**Arms:**
- `adaptive_method` — contextual bandit chooses teaching method
- `fixed_worked_example` — always worked-example first

**Secondary:** method switches across sessions, time-on-task (latency_ms), immediate_post accuracy, integrity fail rate.

**Sample:** N ≈ 12–20 consented adults/teens (protocol reusable for schools later). Not powered for small effects — estimate with CIs and report honestly.

**Exclusion:** sessions with `lesson_ok=false`, incomplete Session 2, or respondent ≠ human (except labeled dry-runs).

**Analysis:** mean delayed accuracy by arm ± 95% bootstrap CI; no claim of child efficacy until a school pilot.

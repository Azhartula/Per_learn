# Evaluation analysis plan (AI platform proof)

**Primary outcome:** delayed-check accuracy (`delayed_24h` / Form C) after a teaching-method assignment.

**Primary cohort for pitching:** Qwen learner agents (`respondent=llm_agent`, N≈12–20 personas).

**Arms:**
- `adaptive_method` — bandit chooses teaching method
- `fixed_worked_example` — always worked-example first

**Secondary:**
- method match vs persona style bias (matched delayed score vs mismatched)
- immediate_post accuracy
- integrity fail rate (`lesson_ok`)
- latency / cost per session

**Exclusion:** sessions with `lesson_ok=false` or incomplete delayed form.

**How to talk about it**

- Lead with: “Our AI learners run the same loop your product would — we measure whether the teaching style stuck, then adapt.”
- Do **not** lead with: “We need to recruit 12–20 people first.”
- Human partner traffic is an optional deployment validation, not the product thesis.

# Method fidelity rubric (human review)

Use this when reviewing a generated lesson before a pilot session.

Score each item 0 / 1 / 2. Lesson must score ≥ 6/8 to ship.

| Criterion | 0 | 1 | 2 |
|-----------|---|---|---|
| Method match | Wrong pedagogy | Partial | Clear match to assigned method |
| Misconception target | Absent | Mentioned weakly | Explicitly addressed |
| Year 5 language | Too hard/vague | Mostly OK | Clear and age-fit |
| Math correctness | Any false claim | Minor slip | Fully correct |

## Method-specific must-haves

- **worked_example:** visible step-by-step solution before practice
- **problem_first:** challenge appears before the reveal/solution
- **visual:** real diagram / number line / bars (ASCII OK) + caption that is true
- **story_analogy:** concrete real-world frame tied to the maths steps

## Hard fails (auto or human)

- Any false magnitude/ordering claim in instructional prose
- `answers_ok=false` or `lesson_ok=false` from integrity checks
- Exit ticket that only restates the worked example verbatim with no new item

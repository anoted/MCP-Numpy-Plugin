---
description: Review Python/NumPy code with a teaching focus (vectorization, correctness, idioms).
argument-hint: [file or directory to review]
---

Perform a NumPy-focused code review. Load and use the `numpy-review` skill if
it is available.

Target: $ARGUMENTS

If no target was given, review the NumPy/Python files most recently changed in
this session (or ask which file to review).

Follow this process:
1. Read the target file(s) fully.
2. Group findings as Correctness → Performance → Style/Idiom, and open with
   something the student did well.
3. For each issue, give a one-line *why* and a short before/after fix.
4. End with 1–2 concrete practice steps.

Teach, don't just correct — the goal is for the student to internalize
idiomatic NumPy.

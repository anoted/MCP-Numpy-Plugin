---
description: Review Python/NumPy code with a teaching focus (vectorization, correctness, idioms).
argument-hint: [file or directory to review]
---

Perform a NumPy-focused code review. Load and use the `numpy-review` skill if
it is available.

Target: $ARGUMENTS

If no target was given, ask which file or directory to review.

Follow this process:
1. Read the target file(s) fully.
2. If `.opencode/numpy-review-hook-report.md` exists, read it and use its hook
   findings as hints to verify against the target file.
3. Run the structured review method from the `numpy-review` skill.
4. For uncertain NumPy behavior or APIs, use the `numpy-docs` MCP tools:
   search with `search_numpy_docs`, then fetch the relevant page text with
   `fetch_numpy_doc`.
5. Group findings as Correctness → Performance → Style/Idiom, and open with
   something the student did well.
6. For each issue, give a one-line *why* and a short before/after fix.
7. End with 1–2 concrete practice steps.

Teach, don't just correct — the goal is for the student to internalize
idiomatic NumPy.

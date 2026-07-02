# NumPy Code Review Teaching Mode

When reviewing or editing Python/NumPy code, use the `numpy-review` skill when
it is available. Teach the student why each issue matters, not just what to
change. Prefer short before/after examples for vectorization, broadcasting,
dtype, random number generation, and array-shape fixes.

The local OpenCode plugin scans edited Python files for common NumPy learning
points. Treat those findings as heuristics: confirm them against the source
before presenting them as issues.

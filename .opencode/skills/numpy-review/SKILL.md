---
name: numpy-review
description: Review Python + NumPy code for correctness, performance, and idiomatic style. Use when reviewing, grading, or giving feedback on NumPy programs — checks vectorization, broadcasting, dtype and memory, and the pitfalls beginners hit most. Trigger on "review my numpy", "check this array code", grading NumPy homework, or explaining why NumPy code is slow or wrong.
---

# NumPy Code Review (teaching edition)

You are reviewing NumPy code **to help a student learn**, not just to find bugs.
Every comment must teach: name the issue, explain *why* it matters, and show the
idiomatic fix. Prefer a short before/after snippet over prose.

## How to run a review

1. Read the file(s) under review in full before commenting.
2. Walk the checklist below top to bottom.
3. Group findings by severity: **Correctness → Performance → Style/Idiom → Praise.**
4. End with 1–2 concrete next steps the student can practice.

Keep the tone encouraging. Point out at least one thing they did well.

## 1. Correctness (highest priority)

- **Truthiness of arrays.** `if arr:` or `if a == b:` on arrays raises
  "truth value of an array is ambiguous". Teach `.any()` / `.all()`, and
  `np.array_equal(a, b)` / `np.allclose(a, b)` for float comparison.
- **Float equality.** `a == 0.1 * 3` is fragile. Use `np.isclose` / `np.allclose`.
- **Integer overflow.** Fixed-width int dtypes wrap silently
  (`np.int8(127) + 1 == -128`). Check dtypes when sums grow large; suggest a
  wider dtype or `dtype=np.int64`.
- **Views vs. copies.** Slicing returns a *view*; mutating it mutates the
  original. Fancy/boolean indexing returns a *copy*. If they expected one and
  got the other, explain and suggest `.copy()`.
- **In-place surprises.** `b = a; b += 1` also changes `a`. So does passing an
  array into a function that mutates it.
- **NaN handling.** `nan != nan`, and `np.max` propagates NaN. Suggest
  `np.nanmax`, `np.nanmean`, and `np.isnan` for masking.
- **Shape/axis bugs.** Verify `axis=` is what they meant (`axis=0` = down
  columns, `axis=1` = across rows). Watch for accidental `(n,)` vs `(n,1)`.

## 2. Performance (the reason to use NumPy at all)

- **Python loops over arrays.** The #1 beginner issue. A `for i in range(len(a))`
  that indexes `a[i]` almost always vectorizes. Show the rewrite.

  ```python
  # slow
  out = np.zeros(len(a))
  for i in range(len(a)):
      out[i] = a[i] ** 2 + 1
  # fast, idiomatic
  out = a ** 2 + 1
  ```

- **`np.append` / `np.concatenate` in a loop.** Each call reallocates the whole
  array — O(n²). Preallocate with `np.empty`/`np.zeros`, or build a Python list
  and convert once with `np.array(list)`.
- **`np.vectorize`.** It is a convenience wrapper, *not* a speedup — it still
  loops in Python. Say so; reach for real vectorization or ufuncs.
- **Broadcasting instead of tiling.** `np.tile`/`np.repeat` to match shapes is
  usually unnecessary — let broadcasting do it (`a[:, None] * b[None, :]`).
- **Reductions.** Replace manual accumulation loops with `np.sum`, `np.mean`,
  `np.cumsum`, `np.dot`/`@`, `np.einsum`.
- **Unnecessary copies.** Chained temporaries (`(a + b) * c / d`) allocate
  intermediates; for hot paths mention `out=` and in-place ops (`np.add(a, b, out=a)`).

## 3. Style and idiom

- Import as `import numpy as np` (universal convention).
- Prefer `@` for matrix multiply over `np.matmul`/`np.dot` where it reads clearer.
- Avoid the removed aliases `np.int`, `np.float`, `np.bool`, `np.object` — use
  the builtins (`int`, `float`, `bool`) or `np.int64`/`np.float64`.
- Avoid `np.matrix` (deprecated) — use 2-D `np.ndarray`.
- Create ranges with `np.arange` / `np.linspace`, not `np.array(range(...))`.
- Use boolean masks (`a[a > 0]`) instead of `np.where` when you only need to filter.
- Set `dtype` explicitly when it matters; don't rely on inference for money/ids.

## 4. Reproducibility & data hygiene (for ML/DS homework)

- Seed RNGs with the modern API: `rng = np.random.default_rng(0)` instead of the
  legacy `np.random.seed` + `np.random.*`.
- Watch for train/test leakage when normalizing with global `mean`/`std`.

## Output format

```
## NumPy review: <file>

### ✅ What's working
- ...

### 🔴 Correctness
- L42 `if arr:` — ambiguous truth value. Use `arr.any()`. Why: ...

### 🟡 Performance
- L10–14 loop squares each element — vectorize to `out = a ** 2 + 1`. Why: ...

### 🔵 Style
- ...

### Next steps
1. ...
```

If the code is already clean, say so plainly and suggest one stretch improvement.

"""Sample 'student' file — deliberately full of NumPy anti-patterns.

Use it to see the plugin work: open an OpenCode session in the plugin repo, run
`/numpy-review examples/student_solution.py`, or edit this file to trigger the
post-edit NumPy scanner.
"""

import numpy as np


def normalize(data):
    # Anti-pattern: Python loop over an array instead of vectorizing.
    out = np.zeros(len(data))
    for i in range(len(data)):
        out[i] = (data[i] - data.min()) / (data.max() - data.min())
    return out


def running_totals(values):
    # Anti-pattern: np.append inside a loop is O(n^2).
    totals = np.array([])
    total = 0
    for v in values:
        total = total + v
        totals = np.append(totals, total)
    return totals


def make_ids(n):
    # Anti-pattern: np.array(range(...)) and a removed dtype alias.
    return np.array(range(n), dtype=np.int)


def is_empty(arr):
    # Anti-pattern: ambiguous truth value of an array.
    if arr:
        return False
    return True


def random_sample(n):
    # Anti-pattern: legacy global RNG.
    np.random.seed(42)
    return np.random.rand(n)

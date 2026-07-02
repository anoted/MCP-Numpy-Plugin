#!/usr/bin/env python3
"""Lightweight NumPy anti-pattern scanner for OpenCode.

The OpenCode plugin calls this after write/edit-style tools. It can also read a
simple hook payload from stdin for manual testing. If the target is a Python
file that uses NumPy, it scans for common beginner anti-patterns.

Findings are advisory only: the script exits 0 even on failure so a student's
workflow is never interrupted by the scanner itself.

Standard library only; no third-party deps.
"""

import argparse
import json
import re
import sys


def load_payload():
    """Read and parse the hook JSON from stdin; return {} on any problem."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def target_path(payload):
    """Pull the edited file path out of the tool_input payload."""
    tool_input = payload.get("tool_input", {}) or {}
    return tool_input.get("file_path") or tool_input.get("path") or ""


# Each rule: (compiled regex, short label, teaching message).
# Messages name the fix so the agent can pass the lesson straight to the student.
RULES = [
    (
        re.compile(r"\bfor\s+\w+\s+in\s+range\s*\(\s*len\s*\("),
        "python-loop-over-array",
        "`for i in range(len(a))` that indexes an array almost always "
        "vectorizes. Replace the loop with a whole-array expression "
        "(e.g. `out = a ** 2 + 1`).",
    ),
    (
        re.compile(r"np\.append\s*\("),
        "np-append",
        "`np.append` in a loop reallocates the whole array each call (O(n^2)). "
        "Preallocate with `np.zeros`/`np.empty`, or build a Python list and "
        "convert once with `np.array(list)`.",
    ),
    (
        re.compile(r"np\.(int|float|bool|object|str)\b(?!\d|_|8|16|32|64|128)"),
        "removed-dtype-alias",
        "`np.int` / `np.float` / `np.bool` were removed in NumPy 1.24. Use the "
        "Python builtins (`int`, `float`, `bool`) or sized dtypes "
        "(`np.int64`, `np.float64`).",
    ),
    (
        re.compile(r"np\.matrix\s*\("),
        "np-matrix",
        "`np.matrix` is deprecated. Use a 2-D `np.ndarray` and the `@` operator "
        "for matrix multiplication.",
    ),
    (
        re.compile(r"np\.vectorize\s*\("),
        "np-vectorize",
        "`np.vectorize` is a convenience wrapper, not a speedup — it still loops "
        "in Python. Prefer true vectorized ops or ufuncs.",
    ),
    (
        re.compile(r"np\.array\s*\(\s*range\s*\("),
        "array-of-range",
        "`np.array(range(n))` builds a Python range first. Use `np.arange(n)` "
        "(or `np.linspace`) directly.",
    ),
    (
        re.compile(r"==\s*None|!=\s*None"),
        "compare-to-none",
        "Compare to None with `is` / `is not`, not `==`/`!=`.",
    ),
    (
        re.compile(r"np\.random\.seed\s*\("),
        "legacy-rng",
        "`np.random.seed` uses the legacy global RNG. Prefer the modern API: "
        "`rng = np.random.default_rng(seed)` then `rng.random(...)` etc.",
    ),
]


def scan(source):
    """Return a list of (line_no, label, message) findings for the source text."""
    findings = []
    lines = source.splitlines()
    for lineno, line in enumerate(lines, start=1):
        # Ignore comment-only lines so we don't flag prose.
        if line.lstrip().startswith("#"):
            continue
        for pattern, label, message in RULES:
            if pattern.search(line):
                findings.append((lineno, label, message))
    return findings


def build_context(path, findings):
    """Format findings for injection into OpenCode tool output."""
    seen = {}
    for lineno, label, message in findings:
        seen.setdefault(label, (lineno, message))

    bullet_lines = [
        f"- L{lineno} [{label}] {message}"
        for label, (lineno, message) in sorted(seen.items(), key=lambda kv: kv[1][0])
    ]

    return (
        "NumPy review plugin flagged potential learning points in "
        f"`{path}`:\n" + "\n".join(bullet_lines) +
        "\n\nMention the relevant ones to the student with a short before/after "
        "fix. These are heuristics; confirm before treating any as a hard error."
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Scan Python/NumPy code for teaching points.")
    parser.add_argument("path", nargs="?", help="Python file to scan")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Print plain text instead of hook JSON",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = {} if args.path else load_payload()
    path = args.path or target_path(payload)

    if not path or not path.endswith(".py"):
        return 0  # not a Python file — nothing to teach here

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            source = fh.read()
    except OSError:
        return 0

    # Only engage when the file actually touches NumPy.
    if "numpy" not in source and re.search(r"\bnp\.", source) is None:
        return 0

    findings = scan(source)
    if not findings:
        return 0

    context = build_context(path, findings)

    if args.text:
        print(context)
        return 0

    print(json.dumps({
        "additionalContext": context,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

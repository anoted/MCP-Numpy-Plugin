# numpy-code-review for OpenCode

An OpenCode teaching plugin for reviewing Python + NumPy code. It helps an
agent review student code for correctness, performance, and idiomatic array
programming, while explaining the reason behind each fix.

## What it includes

| Component | OpenCode location | What it does |
| --- | --- | --- |
| Plugin | `.opencode/plugins/numpy-code-review.js` | Scans changed `.py` files, shows hook output in the TUI, and writes `.opencode/numpy-review-hook-report.md`. |
| Skill | `.opencode/skills/numpy-review/SKILL.md` | Gives the agent a structured review method: correctness, performance, style, and next steps. |
| Command | `.opencode/commands/numpy-review.md` | Adds `/numpy-review [file-or-directory]` as the explicit review workflow using the skill and docs MCP. |
| MCP server | `.opencode/mcp/numpy_docs_server.py` | Adds `numpy-docs` tools to search NumPy docs and fetch page text from `numpy.org/doc`. |
| Instructions | `.opencode/instructions/numpy-code-review.md` | Sets the teaching tone for Python/NumPy work. |

## Repository layout

```text
numpy-review-plugin-opencode/
├── .opencode/
│   ├── commands/
│   │   └── numpy-review.md
│   ├── instructions/
│   │   └── numpy-code-review.md
│   ├── mcp/
│   │   └── numpy_docs_server.py
│   ├── plugins/
│   │   └── numpy-code-review.js
│   ├── scripts/
│   │   └── numpy_review.py
│   └── skills/
│       └── numpy-review/
│           └── SKILL.md
├── examples/
│   └── student_solution.py
├── opencode.json
└── README.md
```

## Requirements

- OpenCode installed and configured.
- Python 3.8+ on your `PATH` as `python`.
- No `pip install` is required. The scanner, plugin, and MCP server use OpenCode
  defaults plus the Python/Node standard libraries.

Check Python with:

```powershell
python --version
```

## Install

### Option A: Use this repo as the project configuration

1. Open a terminal in this folder.
2. Start OpenCode:

```powershell
opencode
```

OpenCode automatically loads:

- local plugins from `.opencode/plugins/`
- commands from `.opencode/commands/`
- skills from `.opencode/skills/`
- MCP servers from `opencode.json`
- instruction files listed in `opencode.json`

### Option B: Install globally for every OpenCode project

Copy the `.opencode` contents into your global OpenCode config directory:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\opencode" | Out-Null
Copy-Item -Recurse -Force ".opencode\*" "$env:USERPROFILE\.config\opencode\"
```

Then copy the MCP config from `opencode.json` into
`$env:USERPROFILE\.config\opencode\opencode.json`. If you already have a global
config, merge the `instructions` and `mcp.numpy-docs` entries instead of
replacing the whole file.

For a global install, update the MCP `cwd` to the absolute global MCP directory,
for example:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "C:/Users/YOU/.config/opencode/instructions/numpy-code-review.md"
  ],
  "mcp": {
    "numpy-docs": {
      "type": "local",
      "command": ["python", "C:/Users/YOU/.config/opencode/mcp/numpy_docs_server.py"],
      "enabled": true,
      "timeout": 15000
    }
  }
}
```

Restart OpenCode after installing or changing config.

## Verify

In OpenCode:

- Type `/` and confirm `/numpy-review` appears.
- Ask to review `examples/student_solution.py` or run:

```text
/numpy-review examples/student_solution.py
```

- Ask OpenCode to search the NumPy docs for broadcasting and confirm it can use
  the `numpy-docs` MCP tool.
- Ask OpenCode to fetch the NumPy docs page for `reshape` and confirm it can use
  `fetch_numpy_doc`.
- Edit `examples/student_solution.py` from an editor. The file-change hook scans
  the changed Python file, shows a TUI toast, inserts a short hook summary into
  the prompt, and updates `.opencode/numpy-review-hook-report.md`.

## Hook behavior

The plugin keeps hooks narrow while still making hook activity visible:

- On `file.edited` and `file.watcher.updated`, it scans changed `.py` files with
  `.opencode/scripts/numpy_review.py`.
- On write/edit-style tool calls, it scans the edited Python file and appends a
  short `[NumPy review hook]` note to the tool output.
- It writes the latest scanner output to `.opencode/numpy-review-hook-report.md`
  so the hook has a concrete, inspectable output artifact. This report is not
  ignored by the plugin template because it demonstrates hook output.
- It shows a `NumPy review hook` TUI toast after file-change scans, including
  the changed file and number of findings written to the report.
- It also inserts a short `[NumPy review hook]` summary into the TUI prompt
  after file-change scans. The hook does not auto-submit anything.
- It does not register read hooks, does not show startup messages, and does not
  use experimental chat hooks.
- `/numpy-review` is the intentional visible review path. It reads the target
  file, reads the hook report when present, applies the `numpy-review` skill,
  and uses the `numpy-docs` MCP tools when documentation is useful.

The hook export is intentionally compatible with OpenCode 1.17.x:

```js
export const server = async ({ directory }) => ({
  event: async ({ event }) => { /* scan changed .py files and update report */ },
  "tool.execute.after": async (input, output) => { /* annotate edit output */ }
})
```

## Manual smoke tests

Run the NumPy scanner directly:

```powershell
python .opencode\scripts\numpy_review.py --text examples\student_solution.py
```

Run the MCP server directly:

```powershell
$messages = @(
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}',
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fetch_numpy_doc","arguments":{"target":"reshape","max_chars":2000}}}'
)
$messages | python .opencode\mcp\numpy_docs_server.py
```

## Customize for class exercises

- Add a new rule to `RULES` in `.opencode/scripts/numpy_review.py`.
- Extend `.opencode/skills/numpy-review/SKILL.md` with a course-specific
  grading rubric.
- Add another command under `.opencode/commands/`.
- Add more documentation tools to the `mcp` block in `opencode.json`.

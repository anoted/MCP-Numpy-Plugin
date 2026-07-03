import { existsSync, mkdirSync, writeFileSync } from "node:fs"
import { dirname, isAbsolute, relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { spawnSync } from "node:child_process"

const PLUGIN_DIR = dirname(fileURLToPath(import.meta.url))
const REVIEW_SCRIPT = resolve(PLUGIN_DIR, "../scripts/numpy_review.py")
const PYTHON = process.env.NUMPY_REVIEW_PYTHON || "python"
const MAX_FILES_PER_EVENT = 8
const REPORT_PATH = ".opencode/numpy-review-hook-report.md"
const EDIT_TOOLS = new Set(["write", "edit", "multiedit", "multi_edit", "patch", "apply_patch"])
const latestFindingsByPath = new Map()

function collectPythonPaths(value, paths = new Set(), depth = 0) {
  if (!value || depth > 8) return paths

  if (typeof value === "string") {
    if (/\.py$/i.test(value)) paths.add(value)
    return paths
  }

  if (Array.isArray(value)) {
    for (const item of value) collectPythonPaths(item, paths, depth + 1)
    return paths
  }

  if (typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      const likelyPathKey = /^(file_?path|filepath|path|paths|files?)$/i.test(key)
      if (likelyPathKey) collectPythonPaths(item, paths, depth + 1)
      else if (typeof item === "object") collectPythonPaths(item, paths, depth + 1)
    }
  }

  return paths
}

function normalizePath(path, directory) {
  const absolute = isAbsolute(path) ? path : resolve(directory, path)
  return existsSync(absolute) && /\.py$/i.test(absolute) ? absolute : undefined
}

function scanFile(path) {
  const result = spawnSync(PYTHON, [REVIEW_SCRIPT, "--text", path], {
    encoding: "utf8",
    timeout: 10_000,
    windowsHide: true,
  })

  if (result.error || result.status !== 0) return ""
  return (result.stdout || "").trim()
}

function defer(task) {
  setTimeout(() => {
    Promise.resolve().then(task).catch(() => {})
  }, 0)
}

function countFindings(text) {
  return text.split("\n").filter((line) => /^- L\d+ /.test(line)).length
}

function showHookToast(client, summaries) {
  if (!client?.tui?.showToast) return

  const fileLabel = summaries.length === 1
    ? summaries[0].file
    : `${summaries.length} Python files`
  const findingCount = summaries.reduce((total, summary) => total + summary.findings, 0)
  const findingLabel = findingCount === 1 ? "1 finding" : `${findingCount} findings`

  defer(() => client.tui.showToast({
    body: {
      title: "NumPy review hook",
      message: `Detected change in ${fileLabel}; ${findingLabel} written to ${REPORT_PATH}.`,
      variant: findingCount ? "warning" : "info",
      duration: 7000,
    },
  }))
}

function appendHookPrompt(client, summaries) {
  if (!client?.tui?.appendPrompt) return

  const lines = summaries.map((summary) => {
    const findingLabel = summary.findings === 1 ? "1 finding" : `${summary.findings} findings`
    return `- ${summary.file}: ${findingLabel}`
  })

  defer(() => client.tui.appendPrompt({
    body: {
      text: [
        "",
        "[NumPy review hook]",
        `Detected Python file change; report updated at ${REPORT_PATH}.`,
        ...lines,
        "",
      ].join("\n"),
    },
  }))
}

export const server = async ({ client, directory }) => {
  const reportPath = resolve(directory, REPORT_PATH)

  const writeReport = () => {
    const sections = [...latestFindingsByPath.entries()].map(([path, text]) => {
      return `## ${relative(directory, path)}\n\n${text}`
    })

    const body = sections.length
      ? sections.join("\n\n")
      : "No current NumPy hook findings."

    mkdirSync(dirname(reportPath), { recursive: true })
    writeFileSync(reportPath, [
      "# NumPy Review Hook Report",
      "",
      `Updated: ${new Date().toISOString()}`,
      "",
      "Source: file-change hook. Use these findings as hints for `/numpy-review`; verify against the file before giving feedback.",
      "",
      body,
      "",
    ].join("\n"), "utf8")
  }

  const scanChangedFiles = (...objects) => {
    const paths = [...collectPythonPaths(objects)]
      .map((path) => normalizePath(path, directory))
      .filter(Boolean)

    const scannedPaths = [...new Set(paths)].slice(0, MAX_FILES_PER_EVENT)
    const summaries = []
    for (const path of scannedPaths) {
      const text = scanFile(path)
      if (text) latestFindingsByPath.set(path, text)
      else latestFindingsByPath.delete(path)
      summaries.push({
        file: relative(directory, path),
        findings: text ? countFindings(text) : 0,
      })
    }

    if (scannedPaths.length) {
      writeReport()
      showHookToast(client, summaries)
      appendHookPrompt(client, summaries)
    }
  }

  return {
    "tool.execute.after": async (input, output) => {
      if (!EDIT_TOOLS.has(String(input?.tool || "").toLowerCase())) return

      scanChangedFiles(input?.args)

      if (typeof output?.output === "string") {
        output.output = `${output.output}\n\n[NumPy review hook]\nEdit hook scanned changed Python file(s). Report updated at ${REPORT_PATH}.`
      }
    },

    event: async ({ event }) => {
      const isFileChange = event?.type === "file.edited" || event?.type === "file.watcher.updated"
      if (!isFileChange || event?.properties?.event === "unlink") return

      scanChangedFiles(event?.properties, event?.data)
    },
  }
}

export const NumpyCodeReview = server
export default server

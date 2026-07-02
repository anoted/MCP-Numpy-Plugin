import { existsSync } from "node:fs"
import { dirname, isAbsolute, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { spawnSync } from "node:child_process"

const PLUGIN_DIR = dirname(fileURLToPath(import.meta.url))
const REVIEW_SCRIPT = resolve(PLUGIN_DIR, "../scripts/numpy_review.py")
const PYTHON = process.env.NUMPY_REVIEW_PYTHON || "python"
const EDIT_TOOLS = new Set(["write", "edit", "multiedit", "multi_edit", "patch", "apply_patch"])

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
    timeout: 15_000,
    windowsHide: true,
  })

  if (result.error) return ""
  if (result.status !== 0) return ""
  return (result.stdout || "").trim()
}

async function log(client, level, message, extra = {}) {
  try {
    await client.app.log({
      body: {
        service: "numpy-code-review",
        level,
        message,
        extra,
      },
    })
  } catch {
    // Logging is best-effort; never let it affect the coding workflow.
  }
}

export const NumpyCodeReview = async ({ client, directory }) => {
  await log(client, "info", "NumPy code review plugin initialized", {
    reviewScript: REVIEW_SCRIPT,
  })

  const scanFromObjects = async (...objects) => {
    const rawPaths = collectPythonPaths(objects)
    const paths = [...rawPaths]
      .map((path) => normalizePath(path, directory))
      .filter(Boolean)

    const findings = []
    for (const path of [...new Set(paths)]) {
      const text = scanFile(path)
      if (text) findings.push(text)
    }
    return findings
  }

  return {
    "tool.execute.after": async (input, output) => {
      if (!EDIT_TOOLS.has(String(input?.tool || "").toLowerCase())) return

      const findings = await scanFromObjects(input, output)
      if (!findings.length) return

      const context = findings.join("\n\n")
      await log(client, "info", "NumPy review findings detected", { context })

      if (typeof output?.output === "string") {
        output.output = `${output.output}\n\n${context}`
      }
    },

    event: async ({ event }) => {
      if (event?.type !== "file.edited" && event?.type !== "file.watcher.updated") return

      const findings = await scanFromObjects(event?.data)
      if (findings.length) {
        await log(client, "info", "NumPy review findings detected from file event", {
          context: findings.join("\n\n"),
        })
      }
    },
  }
}

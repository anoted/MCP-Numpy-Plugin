#!/usr/bin/env python3
"""MCP server: web search scoped to the official NumPy documentation only.

Exposes a single tool, `search_numpy_docs`, which runs a web search that is
*hard-restricted* to https://numpy.org/doc — no matter what the caller passes,
the server appends `site:numpy.org/doc` and strips any `site:` the caller tried
to inject, so results can only come from the NumPy docs.

Why hand-rolled? This is a teaching plugin (Module 5: Hooks & Plugins), so the
server implements the MCP stdio protocol (newline-delimited JSON-RPC 2.0) using
only the Python standard library — no `pip install`, runs anywhere `python`
does. In production you'd typically use the `mcp` SDK / FastMCP instead.

Protocol notes:
  * Transport: one JSON-RPC message per line on stdin/stdout.
  * stdout is reserved for protocol messages ONLY. All logging goes to stderr,
    otherwise the JSON stream gets corrupted and the client disconnects.
"""

import html
import json
import re
import sys
import urllib.parse
import urllib.request

SERVER_NAME = "numpy-docs"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2024-11-05"

# Every query is forced into this documentation subtree. Change nothing else.
DOC_SITE = "numpy.org/doc"
SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def log(*args):
    """Diagnostics to stderr — never stdout."""
    print("[numpy-docs]", *args, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# The actual "search NumPy docs" implementation
# --------------------------------------------------------------------------- #

_ANCHOR_RE = re.compile(r'<a\b([^>]*class="result__a"[^>]*)>(.*?)</a>', re.S)
_SNIPPET_RE = re.compile(r'<a\b[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.S)
_HREF_RE = re.compile(r'href="([^"]+)"')
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(markup):
    text = _TAG_RE.sub("", markup)
    # Decode HTML entities (&#x27; -> ', &amp; -> &, &mdash; -> em dash).
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_ddg_url(href):
    """DuckDuckGo wraps results as //duckduckgo.com/l/?uddg=<encoded>. Unwrap it."""
    if "uddg=" in href:
        qs = urllib.parse.urlparse(href).query
        params = urllib.parse.parse_qs(qs)
        if params.get("uddg"):
            return params["uddg"][0]
    if href.startswith("//"):
        return "https:" + href
    return href


def search_numpy_docs(query, max_results=5):
    """Return formatted top results restricted to the NumPy documentation."""
    query = (query or "").strip()
    if not query:
        return "Please provide a search query (e.g. 'reshape', 'broadcasting rules')."

    # Hard-scope: drop any caller-supplied site: filter, then force ours.
    cleaned = re.sub(r"\bsite:\S+", "", query, flags=re.IGNORECASE).strip()
    scoped_query = f"{cleaned} site:{DOC_SITE}"

    try:
        max_results = max(1, min(int(max_results), 10))
    except (TypeError, ValueError):
        max_results = 5

    data = urllib.parse.urlencode({"q": scoped_query}).encode("utf-8")
    req = urllib.request.Request(
        SEARCH_ENDPOINT,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # network blocked, offline, DDG down, etc.
        return (
            f"Could not reach the search backend ({exc.__class__.__name__}: {exc}).\n"
            "Tip: the API reference for a specific symbol lives at\n"
            f"  https://numpy.org/doc/stable/reference/generated/numpy.<name>.html"
        )

    anchors = _ANCHOR_RE.findall(html)
    snippets = _SNIPPET_RE.findall(html)

    results = []
    for idx, (attrs, title_html) in enumerate(anchors):
        href_match = _HREF_RE.search(attrs)
        if not href_match:
            continue
        url = _decode_ddg_url(href_match.group(1))
        # Belt-and-suspenders: only surface links that really are NumPy docs.
        if "numpy.org/doc" not in url:
            continue
        title = _strip_tags(title_html)
        snippet = _strip_tags(snippets[idx]) if idx < len(snippets) else ""
        results.append((title, url, snippet))
        if len(results) >= max_results:
            break

    if not results:
        return (
            f"No NumPy-docs results for '{cleaned}'. Try a symbol name "
            "(e.g. 'concatenate') or a concept (e.g. 'broadcasting')."
        )

    lines = [f"Top {len(results)} result(s) from numpy.org/doc for '{cleaned}':\n"]
    for i, (title, url, snippet) in enumerate(results, 1):
        lines.append(f"{i}. {title}\n   {url}")
        if snippet:
            lines.append(f"   {snippet[:280]}")
        lines.append("")
    return "\n".join(lines).rstrip()


TOOLS = [
    {
        "name": "search_numpy_docs",
        "description": (
            "Web search restricted to the official NumPy documentation "
            "(numpy.org/doc) only. Use it to look up NumPy functions, array "
            "methods, broadcasting rules, dtypes, and API reference pages. "
            "The search is always scoped to the NumPy docs regardless of input."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look up, e.g. 'reshape', 'broadcasting', 'default_rng'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "How many results to return (1-10, default 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    }
]


# --------------------------------------------------------------------------- #
# Minimal JSON-RPC 2.0 / MCP stdio plumbing
# --------------------------------------------------------------------------- #

def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def result(req_id, payload):
    send({"jsonrpc": "2.0", "id": req_id, "result": payload})


def error(req_id, code, message):
    send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def handle(request):
    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params") or {}

    # Notifications (no id) never get a response.
    if req_id is None and method and method.startswith("notifications/"):
        return

    if method == "initialize":
        client_proto = params.get("protocolVersion", DEFAULT_PROTOCOL)
        result(req_id, {
            "protocolVersion": client_proto,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    elif method == "ping":
        result(req_id, {})
    elif method == "tools/list":
        result(req_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name != "search_numpy_docs":
            error(req_id, -32602, f"Unknown tool: {name}")
            return
        try:
            text = search_numpy_docs(
                arguments.get("query", ""),
                arguments.get("max_results", 5),
            )
            result(req_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as exc:  # never let a tool crash the server
            log("tool error:", exc)
            result(req_id, {
                "content": [{"type": "text", "text": f"Tool error: {exc}"}],
                "isError": True,
            })
    elif req_id is not None:
        error(req_id, -32601, f"Method not found: {method}")


def main():
    log("starting; docs scoped to", DOC_SITE)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            log("skipping non-JSON line")
            continue
        try:
            handle(request)
        except Exception as exc:  # keep the loop alive no matter what
            log("handler error:", exc)


if __name__ == "__main__":
    main()

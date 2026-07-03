#!/usr/bin/env python3
"""MCP server: NumPy documentation search and page fetch tools.

Exposes tools that are hard-restricted to https://numpy.org/doc. Search results
and fetched pages are both limited to official NumPy documentation.

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

DOC_SITE = "numpy.org/doc"
DOC_BASE_URL = "https://numpy.org/doc/stable/"
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
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.S | re.I)


def _strip_tags(markup):
    text = _TAG_RE.sub("", markup)
    # Decode HTML entities (&#x27; -> ', &amp; -> &, &mdash; -> em dash).
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_document_text(markup):
    markup = _SCRIPT_STYLE_RE.sub(" ", markup)
    title_match = _TITLE_RE.search(markup)
    title = _strip_tags(title_match.group(1)) if title_match else "NumPy documentation"
    text = _strip_tags(markup)
    text = re.sub(r"\bSkip to (main )?content\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return title, text


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


def _normalize_doc_url(target):
    target = (target or "").strip()
    if not target:
        raise ValueError("Provide a NumPy documentation URL, path, or symbol.")

    if re.fullmatch(r"(numpy|np)\.[A-Za-z_][\w.]*", target):
        symbol = "numpy." + target.split(".", 1)[1] if target.startswith("np.") else target
        return f"{DOC_BASE_URL}reference/generated/{symbol}.html"

    if re.fullmatch(r"[A-Za-z_]\w*", target):
        return f"{DOC_BASE_URL}reference/generated/numpy.{target}.html"

    if target.startswith("http://") or target.startswith("https://"):
        url = target
    else:
        path = target.lstrip("/")
        if path.startswith("doc/"):
            url = "https://numpy.org/" + path
        else:
            url = urllib.parse.urljoin(DOC_BASE_URL, path)

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "numpy.org" or not parsed.path.startswith("/doc/"):
        raise ValueError("Only https://numpy.org/doc pages can be fetched.")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


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


def fetch_numpy_doc(target, max_chars=12000):
    """Fetch and return text from one official NumPy documentation page."""
    try:
        max_chars = max(1000, min(int(max_chars), 20000))
    except (TypeError, ValueError):
        max_chars = 12000

    try:
        url = _normalize_doc_url(target)
    except ValueError as exc:
        return str(exc)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            markup = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return f"Could not fetch {url} ({exc.__class__.__name__}: {exc})."

    title, text = _clean_document_text(markup)
    if not text:
        return f"Fetched {url}, but could not extract readable text."

    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[truncated]"

    return f"{title}\n{url}\n\n{text}"


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
    },
    {
        "name": "fetch_numpy_doc",
        "description": (
            "Fetch readable text from a specific official NumPy documentation "
            "page. Accepts a full https://numpy.org/doc URL, a docs path such "
            "as 'reference/generated/numpy.reshape.html', or a symbol such as "
            "'reshape' / 'numpy.reshape'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "NumPy docs URL, docs path, or NumPy symbol to fetch.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters of extracted page text to return (1000-20000, default 12000).",
                    "default": 12000,
                },
            },
            "required": ["target"],
        },
    },
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
        try:
            if name == "search_numpy_docs":
                text = search_numpy_docs(
                    arguments.get("query", ""),
                    arguments.get("max_results", 5),
                )
            elif name == "fetch_numpy_doc":
                text = fetch_numpy_doc(
                    arguments.get("target", ""),
                    arguments.get("max_chars", 12000),
                )
            else:
                error(req_id, -32602, f"Unknown tool: {name}")
                return
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

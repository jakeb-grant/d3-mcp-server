import json
import re
import time
from pathlib import Path

import httpx
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from pydantic import BaseModel

from d3_mcp_server.cache import CACHE_DIR, CACHE_TTL_SECONDS
from d3_mcp_server.search import _split_terms

GALLERY_URL = "https://observablehq.com/@d3/gallery"
NOTEBOOK_API_URL = "https://api.observablehq.com"

_GALLERY_CACHE = CACHE_DIR / "_gallery.json"
_EXAMPLES_DIR = CACHE_DIR / "examples"


class D3Example(BaseModel):
    """A D3.js example from the Observable gallery."""

    path: str
    title: str
    category: str
    author: str


# --- Gallery parsing ---

# Matches previews([...]) blocks in the gallery page source
_PREVIEWS_RE = re.compile(r"previews\(\[(.+?)\]\)", re.DOTALL)

# Matches individual example objects inside a previews() block
_EXAMPLE_OBJ_RE = re.compile(
    r"""\{\s*
    path:\s*"([^"]+)",\s*
    thumbnail:\s*"[^"]+",\s*
    title:\s*"([^"]+)",\s*
    author:\s*"([^"]+)"\s*
    \}""",
    re.VERBOSE,
)

# Matches category name from the cell metadata
_CATEGORY_NAME_RE = re.compile(r'"name"\s*:\s*"([^"]+)"')


def _unescape_js(s: str) -> str:
    """Unescape JS string escapes (\\n, \\", etc.)."""
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def parse_gallery(html: str) -> list[D3Example]:
    """Parse the Observable gallery page into a list of D3Examples."""
    unescaped = _unescape_js(html)
    examples: list[D3Example] = []

    # Split by cell boundaries to associate categories with previews
    # The gallery page has cells like: "name":"animation" followed by previews([...])
    # We split on the cell separator pattern and process each chunk
    chunks = re.split(r'\},\{"id":', unescaped)

    for chunk in chunks:
        # Find the category name for this chunk
        cat_match = _CATEGORY_NAME_RE.search(chunk)
        category = cat_match.group(1).capitalize() if cat_match else ""

        # Find all previews blocks in this chunk
        for previews_match in _PREVIEWS_RE.finditer(chunk):
            block = previews_match.group(1)
            for obj_match in _EXAMPLE_OBJ_RE.finditer(block):
                path, title, author = obj_match.groups()
                examples.append(
                    D3Example(
                        path=path,
                        title=title,
                        category=category,
                        author=author,
                    )
                )

    return examples


async def fetch_gallery(ctx: Context | None = None) -> list[D3Example]:
    """Fetch the Observable gallery and return parsed examples.

    Results are cached to disk with 24h TTL.
    """
    if _GALLERY_CACHE.exists():
        age = time.time() - _GALLERY_CACHE.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            data = json.loads(_GALLERY_CACHE.read_text())
            return [D3Example(**item) for item in data]

    if ctx:
        await ctx.info(f"Fetching {GALLERY_URL}...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(GALLERY_URL)
    except httpx.TimeoutException as e:
        msg = f"Timeout fetching {GALLERY_URL}"
        raise ToolError(msg) from e
    except httpx.HTTPError as e:
        msg = f"Network error fetching gallery: {e}"
        raise ToolError(msg) from e

    if response.status_code != 200:
        msg = f"Failed to fetch gallery (HTTP {response.status_code})"
        raise ToolError(msg)

    examples = parse_gallery(response.text)
    if not examples:
        msg = "No examples found in gallery page"
        raise ToolError(msg)

    _GALLERY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _GALLERY_CACHE.write_text(json.dumps([e.model_dump() for e in examples]))

    if ctx:
        await ctx.info(f"Cached {len(examples)} examples")

    return examples


# --- Example scoring ---


def score_examples(
    query: str, examples: list[D3Example]
) -> list[tuple[D3Example, int]]:
    """Score examples against a search query.

    Returns (example, score) pairs sorted by score descending.
    Weights: title word (10), category (3), path keyword (1).
    """
    terms = _split_terms(query)
    results: list[tuple[D3Example, int]] = []

    for example in examples:
        score = 0
        title_lower = example.title.lower()
        title_words = title_lower.split()
        category_lower = example.category.lower()
        path_lower = example.path.lower()

        for term in terms:
            if term in title_words:
                score += 10
            elif term in title_lower:
                score += 5
            if term == category_lower:
                score += 3
            if term in path_lower:
                score += 1

        if score > 0:
            results.append((example, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


# --- Notebook code extraction ---

# Matches named function cells: function _chart(d3,data) { ... }
# or function _data(FileAttachment) { ... }
_FUNC_CELL_RE = re.compile(
    r"^function\s+(_?\w+)\(([^)]*)\)\s*\{",
    re.MULTILINE,
)

# Matches async function cells
_ASYNC_FUNC_CELL_RE = re.compile(
    r"^async\s+function\s+(_?\w+)\(([^)]*)\)\s*\{",
    re.MULTILINE,
)

# Matches markdown cells: function _1(md){return(\nmd`...`\n)}
_MD_CELL_RE = re.compile(
    r"function\s+_\d+\(md\)\s*\{return\(\s*\nmd`(.*?)`\s*\n\)\}",
    re.DOTALL,
)

# Matches arrow-style cells: function _1(md){return( md`...` )}
_MD_CELL_ARROW_RE = re.compile(
    r"function\s+_\d+\(md\)\s*\{return\(\s*md`(.*?)`\s*\)\}",
    re.DOTALL,
)

# Matches FileAttachment mappings in define()
_FILE_ATTACHMENT_RE = re.compile(
    r'\["([^"]+)",\s*\{url:\s*"([^"]+)"(?:,\s*mimeType:\s*"([^"]+)")?\}]'
)


def _extract_function_body(source: str, start: int) -> str:
    """Extract a function body given the position after the opening brace."""
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch in ('"', "'", "`"):
            # Skip string literals
            quote = ch
            i += 1
            while i < len(source):
                if source[i] == "\\" and i + 1 < len(source):
                    i += 2
                    continue
                if source[i] == quote:
                    break
                i += 1
        elif ch == "/" and i + 1 < len(source):
            next_ch = source[i + 1]
            if next_ch == "/":
                # Skip single-line comment
                while i < len(source) and source[i] != "\n":
                    i += 1
            elif next_ch == "*":
                # Skip block comment
                i += 2
                while i + 1 < len(source) and not (
                    source[i] == "*" and source[i + 1] == "/"
                ):
                    i += 1
                i += 1  # skip past /
        i += 1
    return source[start : i - 1].strip() if depth == 0 else ""


def _extract_cell(source: str, name: str) -> tuple[str, str, str] | None:
    """Extract a named cell's parameters and body.

    Returns (name, params, body) or None if not found.
    """
    for pattern in (_ASYNC_FUNC_CELL_RE, _FUNC_CELL_RE):
        for match in pattern.finditer(source):
            if match.group(1) == name:
                params = match.group(2).strip()
                brace_end = match.end()
                body = _extract_function_body(source, brace_end)
                is_async = pattern is _ASYNC_FUNC_CELL_RE
                prefix = "async " if is_async else ""
                return name, params, f"{prefix}{body}"
    return None


def _extract_description(source: str) -> str:
    """Extract the markdown description from the first md cell."""
    for pattern in (_MD_CELL_RE, _MD_CELL_ARROW_RE):
        match = pattern.search(source)
        if match:
            md_content = match.group(1)
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", "", md_content)
            # Strip markdown links but keep text
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            # Strip markdown emphasis
            text = re.sub(r"[*_]+([^*_]+)[*_]+", r"\1", text)
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()
            # Remove the breadcrumb header (D3 > Gallery) and hidden h1
            text = re.sub(r"^.*?D3\s*\u203a\s*Gallery\s*", "", text)
            # Remove leading markdown heading (# Title)
            text = re.sub(r"^#\s+\S[^#]*?\s+", "", text, count=1)
            return text.strip()
    return ""


def _extract_file_attachments(source: str) -> dict[str, str]:
    """Extract FileAttachment name -> URL mappings from define()."""
    attachments: dict[str, str] = {}
    for match in _FILE_ATTACHMENT_RE.finditer(source):
        name, url, _mime = match.groups()
        attachments[name] = url
    return attachments


def _find_chart_dependencies(source: str) -> list[str]:
    """Find what the _chart cell depends on from the define() section."""
    # Match: .define("chart", ["d3","data",...], _chart)
    define_match = re.search(r'\.define\("chart",\s*\[([^\]]*)\],\s*_chart\)', source)
    if define_match:
        deps_str = define_match.group(1)
        return [d.strip().strip('"') for d in deps_str.split(",") if d.strip()]
    return []


def _find_named_cells(source: str) -> list[str]:
    """Find all named (non-underscore-prefixed) cell names from define()."""
    # Pattern: main.variable(observer("name")).define("name", ...)
    names: list[str] = []
    for match in re.finditer(r'observer\("(\w+)"\)\)\.define\("(\w+)"', source):
        name = match.group(1)
        if name not in ("chart",) and not name.startswith("_"):
            names.append(name)
    return names


# Matches module import definitions in define() section
_MODULE_IMPORT_RE = re.compile(r'\.define\("(module \d+)".*?import\("(/[^"?]+)')

# Matches helper imports that reference a module variable
_HELPER_IMPORT_RE = re.compile(
    r'\.define\("(\w+)",\s*\["(module \d+)".*?\.import\("(\w+)"'
)

OBSERVABLE_BASE_URL = "https://observablehq.com"


def _extract_imports(source: str) -> dict[str, str]:
    """Extract imported helper names and their source notebook URLs.

    Returns {helper_name: observable_url}, e.g.
    {"Legend": "https://observablehq.com/@d3/color-legend"}
    """
    # Build module variable → notebook path map
    module_paths: dict[str, str] = {}
    for match in _MODULE_IMPORT_RE.finditer(source):
        module_var, path = match.groups()
        # "/d3/color-legend.js" → "/@d3/color-legend"
        clean = re.sub(r"\.js$", "", path)
        if not clean.startswith("/@"):
            clean = f"/@{clean.lstrip('/')}"
        module_paths[module_var] = clean

    # Map imported names to their source notebook
    imports: dict[str, str] = {}
    for match in _HELPER_IMPORT_RE.finditer(source):
        defined_name, module_var, _imported_name = match.groups()
        if module_var in module_paths:
            notebook_path = module_paths[module_var]
            imports[defined_name] = f"{OBSERVABLE_BASE_URL}{notebook_path}"

    return imports


def extract_notebook_code(source: str) -> str:
    """Parse an Observable notebook .js file and extract clean D3 code.

    Returns a markdown-formatted string with description, code, and data URLs.
    """
    parts: list[str] = []

    # 1. Extract description
    description = _extract_description(source)
    if description:
        parts.append(description)

    # 2. Extract file attachments (data URLs)
    attachments = _extract_file_attachments(source)

    # 3. Extract chart dependencies to find helper cells
    chart_deps = _find_chart_dependencies(source)

    # 4. Extract helper data cells (like _data, _us)
    # and named helper cells that the chart depends on
    helper_code: list[str] = []

    # Find data-loading cells
    for dep in chart_deps:
        if dep in ("d3", "invalidation", "width", "height", "topojson", "DOM"):
            continue
        # Check if there's a function cell for this dependency
        cell = _extract_cell(source, f"_{dep}")
        if cell:
            _, params, body = cell
            if "FileAttachment" in params and attachments:
                # This is a data-loading cell - document it
                helper_code.append(f"// Data: {dep}")
                # Clean the body from Observable patterns
                clean = body.strip()
                if clean.startswith("return(\n") or clean.startswith("return("):
                    clean = re.sub(r"^return\(\s*\n?", "", clean)
                    clean = re.sub(r"\s*\)$", "", clean)
                helper_code.append(f"// {clean}")

    # 5. Extract the main chart function
    chart_cell = _extract_cell(source, "_chart")
    if not chart_cell:
        return "No chart code found in this notebook."

    _, params, body = chart_cell

    # Build the code block
    code_lines: list[str] = []

    # Add parameter info as comment
    param_list = [p.strip() for p in params.split(",") if p.strip()]
    d3_deps = [p for p in param_list if p not in ("d3", "invalidation", "width")]
    if d3_deps:
        code_lines.append(f"// Dependencies: {', '.join(d3_deps)}")

    if helper_code:
        code_lines.extend(helper_code)
        code_lines.append("")

    code_lines.append(body)

    code = "\n".join(code_lines)

    # 6. Assemble the result
    parts.append(f"```js\n{code}\n```")

    # 7. Add imported helpers
    imports = _extract_imports(source)
    if imports:
        parts.append("**Imported helpers:**")
        for name, url in imports.items():
            parts.append(f"- `{name}` from [{url}]({url})")

    # 8. Add data URLs if present
    if attachments:
        parts.append("**Data files:**")
        for name, url in attachments.items():
            parts.append(f"- `{name}`: {url}")

    return "\n\n".join(parts)


# --- Notebook fetching ---


def _example_cache_path(path: str) -> Path:
    """Map an example path like '@d3/bar-chart/2' to a cache file."""
    clean = path.lstrip("@/")
    return _EXAMPLES_DIR / f"{clean}.md"


async def fetch_notebook(path: str, ctx: Context | None = None) -> str:
    """Fetch and extract code from an Observable notebook.

    Args:
        path: Observable path like '@d3/bar-chart/2'.
        ctx: Optional MCP context for logging.
    """
    cache_path = _example_cache_path(path)

    if cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            return cache_path.read_text()

    url = f"{NOTEBOOK_API_URL}/{path}.js?v=4"

    if ctx:
        await ctx.info(f"Fetching {url}...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
    except httpx.TimeoutException as e:
        msg = f"Timeout fetching notebook: {path}"
        raise ToolError(msg) from e
    except httpx.HTTPError as e:
        msg = f"Network error fetching notebook: {e}"
        raise ToolError(msg) from e

    if response.status_code == 404:
        msg = f"Notebook not found: {path}"
        raise ToolError(msg)
    response.raise_for_status()

    content = extract_notebook_code(response.text)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(content)

    if ctx:
        await ctx.info(f"Cached example {path}")

    return content

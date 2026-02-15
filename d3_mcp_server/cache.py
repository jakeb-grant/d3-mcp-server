import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from markdownify import markdownify

from d3_mcp_server.modules import BASE_URL

CACHE_DIR = Path.home() / ".cache" / "d3-mcp-server"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# Collapse 3+ newlines into 2
_EXCESS_NEWLINES = re.compile(r"\n{3,}")


def _cache_path(page: str) -> Path:
    """Map a page path like '/d3-scale/linear' to a cache file."""
    clean = page.lstrip("/")
    return CACHE_DIR / f"{clean}.md"


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_TTL_SECONDS


def _html_to_markdown(html: str) -> str:
    """Extract the doc content from a d3js.org page and convert to markdown."""
    soup = BeautifulSoup(html, "html.parser")

    # d3js.org uses VitePress — content is in <main class="main">
    main = soup.find("main", class_="main")
    if not main:
        # Fallback: try div.vp-doc
        main = soup.find("div", class_="vp-doc")
    if not main:
        # Last resort: use the whole body
        main = soup.body or soup

    # Remove elements that shouldn't appear in docs
    for tag in main.find_all(["script", "style", "img"]):
        tag.decompose()

    md = markdownify(str(main), heading_style="ATX")
    return _EXCESS_NEWLINES.sub("\n\n", md).strip()


async def fetch_page(
    page: str,
    ctx: Context | None = None,
) -> str:
    """Fetch a d3js.org doc page, using a file cache with 24h TTL.

    Args:
        page: Page path like '/d3-scale/linear'.
        ctx: Optional MCP context for logging.
    """
    path = _cache_path(page)

    if _is_fresh(path):
        return path.read_text()

    url = f"{BASE_URL}{page}"

    if ctx:
        await ctx.info(f"Fetching {url}...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
    except httpx.TimeoutException as e:
        msg = f"Timeout fetching {url}"
        raise ToolError(msg) from e
    except httpx.HTTPError as e:
        msg = f"Network error fetching {url}: {e}"
        raise ToolError(msg) from e

    if response.status_code == 404:
        msg = f"Page not found: {url}"
        raise ToolError(msg)
    response.raise_for_status()

    content = _html_to_markdown(response.text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

    if ctx:
        await ctx.info(f"Cached {page} ({len(content)} bytes)")

    return content

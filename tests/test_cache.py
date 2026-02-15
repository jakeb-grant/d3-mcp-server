import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastmcp.exceptions import ToolError

from d3_mcp_server.cache import (
    CACHE_TTL_SECONDS,
    _cache_path,
    _html_to_markdown,
    _is_fresh,
    fetch_page,
)

# --- HTML to markdown tests ---


class TestHtmlToMarkdown:
    def test_extracts_main_content(self) -> None:
        html = """
        <html><body>
        <nav>Navigation</nav>
        <main class="main">
            <h1>d3-scale</h1>
            <p>Scales map data to visual encodings.</p>
        </main>
        <footer>Footer</footer>
        </body></html>
        """
        md = _html_to_markdown(html)
        assert "d3-scale" in md
        assert "Scales map data" in md
        assert "Navigation" not in md
        assert "Footer" not in md

    def test_falls_back_to_vp_doc(self) -> None:
        html = """
        <html><body>
        <div class="vp-doc">
            <h2>API Reference</h2>
            <p>Details here.</p>
        </div>
        </body></html>
        """
        md = _html_to_markdown(html)
        assert "API Reference" in md
        assert "Details here" in md

    def test_falls_back_to_body(self) -> None:
        html = """
        <html><body>
        <h2>Fallback content</h2>
        <p>No main or vp-doc here.</p>
        </body></html>
        """
        md = _html_to_markdown(html)
        assert "Fallback content" in md

    def test_strips_images_scripts_styles(self) -> None:
        html = """
        <main class="main">
            <p>Keep this.</p>
            <img src="chart.png" alt="chart">
            <script>alert('xss')</script>
            <style>.hide { display: none }</style>
        </main>
        """
        md = _html_to_markdown(html)
        assert "Keep this" in md
        assert "chart.png" not in md
        assert "alert" not in md
        assert "display" not in md

    def test_collapses_excess_newlines(self) -> None:
        html = """
        <main class="main">
            <p>First</p>
            <br><br><br><br><br>
            <p>Second</p>
        </main>
        """
        md = _html_to_markdown(html)
        assert "\n\n\n" not in md


# --- Cache path tests ---


class TestCachePath:
    def test_maps_page_to_file(self) -> None:
        path = _cache_path("/d3-scale/linear")
        assert path.name == "linear.md"
        assert "d3-scale" in str(path)

    def test_index_page(self) -> None:
        path = _cache_path("/d3-scale")
        assert path.name == "d3-scale.md"

    def test_strips_leading_slash(self) -> None:
        p1 = _cache_path("/d3-array")
        p2 = _cache_path("d3-array")
        assert p1 == p2


# --- Cache freshness tests ---


class TestIsFresh:
    def test_nonexistent_file(self, tmp_path: Path) -> None:
        assert _is_fresh(tmp_path / "nope.md") is False

    def test_fresh_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("content")
        assert _is_fresh(f) is True

    def test_stale_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("content")
        stale_time = time.time() - CACHE_TTL_SECONDS - 1
        import os

        os.utime(f, (stale_time, stale_time))
        assert _is_fresh(f) is False


# --- fetch_page tests ---


FAKE_HTML = """
<html><body>
<main class="main">
    <h1>d3-color</h1>
    <p>Color spaces and conversions.</p>
</main>
</body></html>
"""


class TestFetchPage:
    @pytest.mark.asyncio
    async def test_fetches_and_caches(self, tmp_path: Path) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = FAKE_HTML
        mock_response.raise_for_status = lambda: None

        with (
            patch("d3_mcp_server.cache.CACHE_DIR", tmp_path),
            patch("d3_mcp_server.cache.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await fetch_page("/d3-color")

        assert "d3-color" in result
        assert "Color spaces" in result

    @pytest.mark.asyncio
    async def test_returns_cached_on_second_call(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "d3-color.md"
        cache_file.write_text("cached content")

        with patch("d3_mcp_server.cache.CACHE_DIR", tmp_path):
            result = await fetch_page("/d3-color")

        assert result == "cached content"

    @pytest.mark.asyncio
    async def test_404_raises_tool_error(self, tmp_path: Path) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 404

        with (
            patch("d3_mcp_server.cache.CACHE_DIR", tmp_path),
            patch("d3_mcp_server.cache.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ToolError, match="Page not found"):
                await fetch_page("/d3-fake")

    @pytest.mark.asyncio
    async def test_timeout_raises_tool_error(self, tmp_path: Path) -> None:
        with (
            patch("d3_mcp_server.cache.CACHE_DIR", tmp_path),
            patch("d3_mcp_server.cache.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ReadTimeout("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ToolError, match="Timeout"):
                await fetch_page("/d3-scale")

    @pytest.mark.asyncio
    async def test_connection_error_raises_tool_error(self, tmp_path: Path) -> None:
        with (
            patch("d3_mcp_server.cache.CACHE_DIR", tmp_path),
            patch("d3_mcp_server.cache.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ToolError, match="Network error"):
                await fetch_page("/d3-scale")

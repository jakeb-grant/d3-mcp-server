from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ToolError

from d3_mcp_server.server import find_module, get_docs, search_docs

# --- find_module tests ---


class TestFindModule:
    @pytest.mark.asyncio
    async def test_lists_all_modules(self) -> None:
        result = await find_module()
        assert "d3-scale" in result
        assert "d3-shape" in result
        assert "d3-array" in result
        assert "Available D3 modules" in result

    @pytest.mark.asyncio
    async def test_search_by_keyword(self) -> None:
        result = await find_module("scale")
        assert "d3-scale" in result
        assert "Modules matching" in result

    @pytest.mark.asyncio
    async def test_no_match(self) -> None:
        result = await find_module("zzzznotfound")
        assert "No modules found" in result


# --- get_docs tests ---


FAKE_INDEX = "# d3-scale\n\nScales map data."
FAKE_SUBPAGE = "# Linear Scales\n\nLinear scale details."


class TestGetDocs:
    @pytest.mark.asyncio
    async def test_unknown_module_raises(self) -> None:
        with pytest.raises(ToolError, match="Unknown module"):
            await get_docs("nonexistent")

    @pytest.mark.asyncio
    async def test_fetches_module_index(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_page",
            new_callable=AsyncMock,
            return_value=FAKE_INDEX,
        ):
            result = await get_docs("d3-scale")
        assert "d3-scale" in result
        assert "Sub-pages" in result

    @pytest.mark.asyncio
    async def test_short_name_works(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_page",
            new_callable=AsyncMock,
            return_value=FAKE_INDEX,
        ):
            result = await get_docs("scale")
        assert "d3-scale" in result

    @pytest.mark.asyncio
    async def test_fetches_subpage(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_page",
            new_callable=AsyncMock,
            return_value=FAKE_SUBPAGE,
        ):
            result = await get_docs("d3-scale", page="linear")
        assert "Linear" in result

    @pytest.mark.asyncio
    async def test_unknown_page_raises_with_available(self) -> None:
        with pytest.raises(ToolError, match="Available"):
            await get_docs("d3-scale", page="nonexistent")

    @pytest.mark.asyncio
    async def test_single_page_module_no_subpages(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_page",
            new_callable=AsyncMock,
            return_value="# d3-brush\n\nBrush docs.",
        ):
            result = await get_docs("d3-brush")
        assert "Sub-pages" not in result


# --- search_docs tests ---


FAKE_SEARCHABLE = """\
## Linear Scales

Linear scales map a continuous domain to a continuous range.

## Log Scales

Log scales are similar to linear scales but use a logarithmic transform.
"""


class TestSearchDocs:
    @pytest.mark.asyncio
    async def test_search_within_module(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_page",
            new_callable=AsyncMock,
            return_value=FAKE_SEARCHABLE,
        ):
            result = await search_docs("linear", module_name="d3-scale")
        assert "Linear" in result

    @pytest.mark.asyncio
    async def test_unknown_module_raises(self) -> None:
        with pytest.raises(ToolError, match="Unknown module"):
            await search_docs("linear", module_name="nonexistent")

    @pytest.mark.asyncio
    async def test_no_results(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_page",
            new_callable=AsyncMock,
            return_value="# Empty\n\nNothing relevant here.",
        ):
            result = await search_docs("zzzznotfound", module_name="d3-brush")
        assert "No results" in result

    @pytest.mark.asyncio
    async def test_search_across_modules(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_page",
            new_callable=AsyncMock,
            return_value=FAKE_SEARCHABLE,
        ):
            result = await search_docs("linear")
        assert "Linear" in result

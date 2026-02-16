from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ToolError

from d3_mcp_server.examples import (
    D3Example,
    _example_cache_path,
    _extract_description,
    _extract_file_attachments,
    _extract_imports,
    extract_notebook_code,
    fetch_gallery,
    fetch_notebook,
    parse_gallery,
    score_examples,
)
from d3_mcp_server.server import find_example, get_example

# --- Fixtures ---

SAMPLE_GALLERY_HTML = (
    '{"nodes":[{"id":100,"value":"### Animation\\n\\n'
    "D3's data join enables smooth transitions.\\n\\n"
    "${previews([\\n"
    "{\\n"
    '  path: \\"@d3/animated-treemap\\",\\n'
    '  thumbnail: \\"abc123\\",\\n'
    '  title: \\"Animated treemap\\",\\n'
    '  author: \\"D3\\"\\n'
    "},\\n"
    "{\\n"
    '  path: \\"@d3/bar-chart-race\\",\\n'
    '  thumbnail: \\"def456\\",\\n'
    '  title: \\"Bar chart race\\",\\n'
    '  author: \\"D3\\"\\n'
    "}\\n"
    '])}","pinned":false,"mode":"md","data":null,"name":"animation"},'
    '{"id":200,"value":"### Bars\\n\\n'
    "D3 scales and axes support basic charts.\\n\\n"
    "${previews([\\n"
    "{\\n"
    '  path: \\"@d3/bar-chart/2\\",\\n'
    '  thumbnail: \\"ghi789\\",\\n'
    '  title: \\"Bar chart\\",\\n'
    '  author: \\"D3\\"\\n'
    "},\\n"
    "{\\n"
    '  path: \\"@mbostock/electric-usage-2019\\",\\n'
    '  thumbnail: \\"jkl012\\",\\n'
    '  title: \\"Electricity usage, 2019\\",\\n'
    '  author: \\"Mike Bostock\\"\\n'
    "}\\n"
    '])}","pinned":false,"mode":"md","data":null,"name":"bars"}]}'
)

SAMPLE_NOTEBOOK_JS = """\
function _1(md){return(
md`<div style="color: grey; font: 13px/25.5px var(--sans-serif); text-transform: uppercase;"><h1 style="display: none;">Bar chart</h1><a href="https://d3js.org/">D3</a> \u203a <a href="/@d3/gallery">Gallery</a></div>

# Bar chart

This chart shows the relative frequency of letters in the English language.`
)}

function _chart(d3,data)
{
  const width = 928;
  const height = 500;

  const x = d3.scaleBand()
      .domain(d3.groupSort(data, ([d]) => -d.frequency, (d) => d.letter))
      .range([0, width])
      .padding(0.1);

  const svg = d3.create("svg")
      .attr("width", width)
      .attr("height", height);

  svg.selectAll("rect")
    .data(data)
    .join("rect")
      .attr("x", (d) => x(d.letter))
      .attr("width", x.bandwidth());

  return svg.node();
}


function _data(FileAttachment){return(
FileAttachment("alphabet.csv").csv({typed: "auto"})
)}

export default function define(runtime, observer) {
  const main = runtime.module();
  const fileAttachments = new Map([
    ["alphabet.csv", {url: "https://static.observableusercontent.com/files/abc123", mimeType: "text/csv"}]
  ]);
  main.builtin("FileAttachment", runtime.fileAttachments(name => fileAttachments.get(name)));
  main.variable(observer()).define(["md"], _1);
  main.variable(observer("chart")).define("chart", ["d3","data"], _chart);
  main.variable(observer("data")).define("data", ["FileAttachment"], _data);
  return main;
}
"""

SAMPLE_NOTEBOOK_WITH_DEPS = """\
function _1(md){return(
md`# Force-directed graph

This network of character co-occurence in Les Misérables.`
)}

function _chart(d3,data,invalidation)
{
  const width = 928;
  const simulation = d3.forceSimulation(data.nodes)
      .force("link", d3.forceLink(data.links).id(d => d.id));

  invalidation.then(() => simulation.stop());

  return d3.create("svg").node();
}


function _data(FileAttachment){return(
FileAttachment("miserables.json").json()
)}

export default function define(runtime, observer) {
  const main = runtime.module();
  const fileAttachments = new Map([
    ["miserables.json", {url: "https://static.observableusercontent.com/files/xyz789", mimeType: "application/json"}]
  ]);
  main.builtin("FileAttachment", runtime.fileAttachments(name => fileAttachments.get(name)));
  main.variable(observer()).define(["md"], _1);
  main.variable(observer("chart")).define("chart", ["d3","data","invalidation"], _chart);
  main.variable(observer("data")).define("data", ["FileAttachment"], _data);
  return main;
}
"""


# --- Gallery parsing tests ---


class TestParseGallery:
    def test_parses_examples(self) -> None:
        examples = parse_gallery(SAMPLE_GALLERY_HTML)
        assert len(examples) == 4

    def test_assigns_categories(self) -> None:
        examples = parse_gallery(SAMPLE_GALLERY_HTML)
        animation = [e for e in examples if e.category == "Animation"]
        bars = [e for e in examples if e.category == "Bars"]
        assert len(animation) == 2
        assert len(bars) == 2

    def test_extracts_fields(self) -> None:
        examples = parse_gallery(SAMPLE_GALLERY_HTML)
        bar = next(e for e in examples if e.path == "@d3/bar-chart/2")
        assert bar.title == "Bar chart"
        assert bar.author == "D3"
        assert bar.category == "Bars"

    def test_handles_non_d3_authors(self) -> None:
        examples = parse_gallery(SAMPLE_GALLERY_HTML)
        electric = next(
            e for e in examples if e.path == "@mbostock/electric-usage-2019"
        )
        assert electric.author == "Mike Bostock"

    def test_empty_html_returns_empty(self) -> None:
        assert parse_gallery("<html></html>") == []


# --- Example scoring tests ---


@pytest.fixture
def sample_examples() -> list[D3Example]:
    return [
        D3Example(
            path="@d3/bar-chart/2",
            title="Bar chart",
            category="Bars",
            author="D3",
        ),
        D3Example(
            path="@d3/treemap/2",
            title="Treemap",
            category="Hierarchies",
            author="D3",
        ),
        D3Example(
            path="@d3/force-directed-graph/2",
            title="Force-directed graph",
            category="Networks",
            author="D3",
        ),
        D3Example(
            path="@d3/line-chart/2",
            title="Line chart",
            category="Lines",
            author="D3",
        ),
    ]


class TestScoreExamples:
    def test_title_match(self, sample_examples: list[D3Example]) -> None:
        results = score_examples("bar", sample_examples)
        assert results[0][0].path == "@d3/bar-chart/2"

    def test_category_match(self, sample_examples: list[D3Example]) -> None:
        results = score_examples("bars", sample_examples)
        assert any(ex.category == "Bars" for ex, _ in results)

    def test_no_match(self, sample_examples: list[D3Example]) -> None:
        results = score_examples("zzzznotfound", sample_examples)
        assert results == []

    def test_sorted_by_score(self, sample_examples: list[D3Example]) -> None:
        results = score_examples("chart", sample_examples)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_multi_word_query(self, sample_examples: list[D3Example]) -> None:
        results = score_examples("bar chart", sample_examples)
        assert results[0][0].path == "@d3/bar-chart/2"

    def test_camel_case_splits(self, sample_examples: list[D3Example]) -> None:
        results = score_examples("barChart", sample_examples)
        assert len(results) > 0
        assert results[0][0].path == "@d3/bar-chart/2"

    def test_camel_case_line_chart(self, sample_examples: list[D3Example]) -> None:
        results = score_examples("lineChart", sample_examples)
        assert len(results) > 0
        assert results[0][0].path == "@d3/line-chart/2"


# --- Notebook code extraction tests ---


class TestExtractDescription:
    def test_extracts_description_text(self) -> None:
        desc = _extract_description(SAMPLE_NOTEBOOK_JS)
        assert "relative frequency" in desc
        assert "English language" in desc

    def test_strips_html(self) -> None:
        desc = _extract_description(SAMPLE_NOTEBOOK_JS)
        assert "<div" not in desc
        assert "<h1" not in desc

    def test_strips_breadcrumb(self) -> None:
        desc = _extract_description(SAMPLE_NOTEBOOK_JS)
        assert "Gallery" not in desc


class TestExtractFileAttachments:
    def test_extracts_urls(self) -> None:
        attachments = _extract_file_attachments(SAMPLE_NOTEBOOK_JS)
        assert "alphabet.csv" in attachments
        assert "abc123" in attachments["alphabet.csv"]

    def test_multiple_attachments(self) -> None:
        source = """
  const fileAttachments = new Map([
    ["a.json", {url: "https://example.com/a", mimeType: "application/json"}],
    ["b.csv", {url: "https://example.com/b", mimeType: "text/csv"}]
  ]);
"""
        attachments = _extract_file_attachments(source)
        assert len(attachments) == 2

    def test_no_attachments(self) -> None:
        assert _extract_file_attachments("no file attachments here") == {}


class TestExtractImports:
    def test_extracts_imported_helper(self) -> None:
        source = """
export default function define(runtime, observer) {
  const main = runtime.module();
  main.define("module 1", async () => runtime.module((await import("/@d3/color-legend.js?v=4&resolutions=abc@123")).default));
  main.define("Legend", ["module 1", "@variable"], (_, v) => v.import("Legend", _));
  return main;
}
"""
        imports = _extract_imports(source)
        assert "Legend" in imports
        assert "observablehq.com/@d3/color-legend" in imports["Legend"]

    def test_multiple_imports(self) -> None:
        source = """
  main.define("module 1", async () => runtime.module((await import("/@d3/color-legend.js?v=4")).default));
  main.define("module 2", async () => runtime.module((await import("/@d3/swatches.js?v=4")).default));
  main.define("Legend", ["module 1", "@variable"], (_, v) => v.import("Legend", _));
  main.define("Swatches", ["module 2", "@variable"], (_, v) => v.import("Swatches", _));
"""
        imports = _extract_imports(source)
        assert len(imports) == 2
        assert "Legend" in imports
        assert "Swatches" in imports

    def test_no_imports(self) -> None:
        assert _extract_imports("no imports here") == {}

    def test_included_in_notebook_output(self) -> None:
        source = (
            SAMPLE_NOTEBOOK_JS
            + """
  main.define("module 1", async () => runtime.module((await import("/@d3/color-legend.js?v=4")).default));
  main.define("Legend", ["module 1", "@variable"], (_, v) => v.import("Legend", _));
"""
        )
        result = extract_notebook_code(source)
        assert "Imported helpers" in result
        assert "Legend" in result
        assert "observablehq.com/@d3/color-legend" in result


class TestExtractNotebookCode:
    def test_contains_chart_code(self) -> None:
        result = extract_notebook_code(SAMPLE_NOTEBOOK_JS)
        assert "scaleBand" in result
        assert "svg" in result

    def test_contains_description(self) -> None:
        result = extract_notebook_code(SAMPLE_NOTEBOOK_JS)
        assert "relative frequency" in result

    def test_contains_data_urls(self) -> None:
        result = extract_notebook_code(SAMPLE_NOTEBOOK_JS)
        assert "alphabet.csv" in result

    def test_contains_code_block(self) -> None:
        result = extract_notebook_code(SAMPLE_NOTEBOOK_JS)
        assert "```js" in result
        assert "```" in result

    def test_handles_dependencies(self) -> None:
        result = extract_notebook_code(SAMPLE_NOTEBOOK_WITH_DEPS)
        assert "forceSimulation" in result

    def test_no_chart_cell(self) -> None:
        result = extract_notebook_code("function _1(md){return(md`hello`)}")
        assert "No chart code" in result

    def test_data_dependency_documented(self) -> None:
        result = extract_notebook_code(SAMPLE_NOTEBOOK_JS)
        assert "data" in result


# --- Cache path tests ---


class TestExampleCachePath:
    def test_maps_path_to_file(self) -> None:
        path = _example_cache_path("@d3/bar-chart/2")
        assert path.name == "2.md"
        assert "bar-chart" in str(path)

    def test_strips_at_sign(self) -> None:
        path = _example_cache_path("@d3/treemap/2")
        assert "@" not in str(path)


# --- fetch_gallery tests ---


class TestFetchGallery:
    @pytest.mark.asyncio
    async def test_fetches_and_caches(self, tmp_path: Path) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_GALLERY_HTML

        with (
            patch("d3_mcp_server.examples.CACHE_DIR", tmp_path),
            patch("d3_mcp_server.examples._GALLERY_CACHE", tmp_path / "_gallery.json"),
            patch("d3_mcp_server.examples.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            examples = await fetch_gallery()

        assert len(examples) == 4
        assert any(e.path == "@d3/bar-chart/2" for e in examples)

    @pytest.mark.asyncio
    async def test_returns_cached(self, tmp_path: Path) -> None:
        import json

        data = [
            {
                "path": "@d3/test",
                "title": "Test",
                "category": "Test",
                "author": "D3",
            }
        ]
        cache_file = tmp_path / "_gallery.json"
        cache_file.write_text(json.dumps(data))

        with (
            patch("d3_mcp_server.examples._GALLERY_CACHE", cache_file),
            patch("d3_mcp_server.examples.CACHE_TTL_SECONDS", 99999),
        ):
            examples = await fetch_gallery()

        assert len(examples) == 1
        assert examples[0].path == "@d3/test"


# --- fetch_notebook tests ---


class TestFetchNotebook:
    @pytest.mark.asyncio
    async def test_fetches_and_extracts(self, tmp_path: Path) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_NOTEBOOK_JS
        mock_response.raise_for_status = lambda: None

        with (
            patch("d3_mcp_server.examples._EXAMPLES_DIR", tmp_path / "examples"),
            patch("d3_mcp_server.examples.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await fetch_notebook("@d3/bar-chart/2")

        assert "scaleBand" in result

    @pytest.mark.asyncio
    async def test_404_raises_tool_error(self, tmp_path: Path) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 404

        with (
            patch("d3_mcp_server.examples._EXAMPLES_DIR", tmp_path / "examples"),
            patch("d3_mcp_server.examples.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(ToolError, match="not found"):
                await fetch_notebook("@d3/nonexistent")


# --- Tool integration tests ---


class TestFindExample:
    @pytest.mark.asyncio
    async def test_lists_categories(self) -> None:
        examples = [
            D3Example(path="@d3/a", title="A", category="Bars", author="D3"),
            D3Example(path="@d3/b", title="B", category="Bars", author="D3"),
            D3Example(path="@d3/c", title="C", category="Lines", author="D3"),
        ]
        with patch(
            "d3_mcp_server.server.fetch_gallery",
            new_callable=AsyncMock,
            return_value=examples,
        ):
            result = await find_example()
        assert "Bars" in result
        assert "Lines" in result

    @pytest.mark.asyncio
    async def test_search_by_query(self) -> None:
        examples = [
            D3Example(
                path="@d3/bar-chart/2",
                title="Bar chart",
                category="Bars",
                author="D3",
            ),
        ]
        with patch(
            "d3_mcp_server.server.fetch_gallery",
            new_callable=AsyncMock,
            return_value=examples,
        ):
            result = await find_example(query="bar")
        assert "Bar chart" in result

    @pytest.mark.asyncio
    async def test_filter_by_category(self) -> None:
        examples = [
            D3Example(
                path="@d3/bar-chart",
                title="Bar chart",
                category="Bars",
                author="D3",
            ),
            D3Example(
                path="@d3/line-chart",
                title="Line chart",
                category="Lines",
                author="D3",
            ),
        ]
        with patch(
            "d3_mcp_server.server.fetch_gallery",
            new_callable=AsyncMock,
            return_value=examples,
        ):
            result = await find_example(category="Bars")
        assert "Bar chart" in result
        assert "Line chart" not in result


class TestGetExample:
    @pytest.mark.asyncio
    async def test_returns_code(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_notebook",
            new_callable=AsyncMock,
            return_value="```js\nconst svg = d3.create('svg');\n```",
        ):
            result = await get_example("@d3/bar-chart/2")
        assert "d3.create" in result
        assert "@d3/bar-chart/2" in result

    @pytest.mark.asyncio
    async def test_adds_at_prefix(self) -> None:
        with patch(
            "d3_mcp_server.server.fetch_notebook",
            new_callable=AsyncMock,
            return_value="code",
        ) as mock_fetch:
            await get_example("d3/bar-chart/2")
        mock_fetch.assert_called_once_with("@d3/bar-chart/2", None)

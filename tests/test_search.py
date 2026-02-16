import pytest

from d3_mcp_server.modules import (
    D3_MODULES,
    D3_PAGE_MAP,
    D3Module,
    resolve_module_name,
    resolve_page_path,
)
from d3_mcp_server.search import Section, parse_sections, score_modules, search_sections

# --- Fixtures ---

SAMPLE_MARKDOWN = """\
# d3-scale

Scales map abstract data to visual representation.

## Continuous Scales

Continuous scales map a continuous, quantitative input domain to a continuous output range.

<a name="scaleLinear" href="#scaleLinear">#</a> d3.<b>scaleLinear</b>() · [Source](src/linear.js)

Constructs a new continuous scale with the unit domain [0, 1] and the unit range [0, 1].

<a name="continuous_domain" href="#continuous_domain">#</a> <i>continuous</i>.<b>domain</b>([<i>domain</i>])

If domain is specified, sets the scale's domain to the specified array of numbers.

### Clamping

If clamping is enabled, the return value of the scale is always within the scale's range.

## Sequential Scales

Sequential scales map a continuous domain to an interpolator.

<a name="scaleSequential" href="#scaleSequential">#</a> d3.<b>scaleSequential</b>([[<i>domain</i>, ]<i>interpolator</i>])

Constructs a new sequential scale with the specified domain and interpolator.
"""


@pytest.fixture
def sample_modules() -> list[D3Module]:
    return [
        D3Module(
            name="d3-scale",
            description="Encodings that map abstract data to visual representation.",
            tags=["scale", "linear", "log", "ordinal"],
            pages=["/d3-scale", "/d3-scale/linear"],
        ),
        D3Module(
            name="d3-shape",
            description="Graphical primitives for visualization.",
            tags=["shape", "arc", "pie", "line", "area", "curve"],
            pages=["/d3-shape", "/d3-shape/arc"],
        ),
        D3Module(
            name="d3-color",
            description="Color spaces including RGB, HSL, Cubehelix, CIELAB.",
            tags=["color", "rgb", "hsl", "lab"],
            pages=["/d3-color"],
        ),
    ]


# --- Module scoring tests ---


class TestScoreModules:
    def test_exact_name_match(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("d3-scale", sample_modules)
        assert results[0][0].name == "d3-scale"
        assert results[0][1] >= 10

    def test_short_name_match(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("scale", sample_modules)
        assert results[0][0].name == "d3-scale"

    def test_tag_match(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("linear", sample_modules)
        assert results[0][0].name == "d3-scale"

    def test_no_match(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("zzzznotfound", sample_modules)
        assert results == []

    def test_sorted_by_score_descending(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("color", sample_modules)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_description_word_match(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("Graphical", sample_modules)
        assert results[0][0].name == "d3-shape"

    def test_camel_case_splits(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("scaleLinear", sample_modules)
        assert len(results) > 0
        assert results[0][0].name == "d3-scale"

    def test_camel_case_multi_word(self, sample_modules: list[D3Module]) -> None:
        results = score_modules("scaleOrdinal", sample_modules)
        assert len(results) > 0
        assert results[0][0].name == "d3-scale"


# --- Section parsing tests ---


class TestParseSections:
    def test_parses_markdown_headings(self) -> None:
        sections = parse_sections(SAMPLE_MARKDOWN)
        headings = [s.heading for s in sections]
        assert "Continuous Scales" in headings
        assert "Sequential Scales" in headings

    def test_parses_html_anchors(self) -> None:
        sections = parse_sections(SAMPLE_MARKDOWN)
        headings = [s.heading for s in sections]
        assert "scaleLinear" in headings
        assert "scaleSequential" in headings

    def test_parses_mixed_content(self) -> None:
        sections = parse_sections(SAMPLE_MARKDOWN)
        # Should have both heading-based and anchor-based sections
        assert len(sections) >= 5

    def test_section_content_not_empty(self) -> None:
        sections = parse_sections(SAMPLE_MARKDOWN)
        for section in sections:
            assert section.content, f"Section '{section.heading}' has empty content"

    def test_subsection_heading(self) -> None:
        sections = parse_sections(SAMPLE_MARKDOWN)
        headings = [s.heading for s in sections]
        assert "Clamping" in headings


# --- Section search tests ---


class TestSearchSections:
    @pytest.fixture
    def sections(self) -> list[Section]:
        return parse_sections(SAMPLE_MARKDOWN)

    def test_heading_match(self, sections: list[Section]) -> None:
        results = search_sections("scaleLinear", sections)
        assert len(results) > 0
        assert results[0].heading == "scaleLinear"

    def test_content_match(self, sections: list[Section]) -> None:
        results = search_sections("domain", sections)
        assert len(results) > 0

    def test_multi_keyword(self, sections: list[Section]) -> None:
        results = search_sections("continuous domain", sections)
        assert len(results) > 0

    def test_no_match(self, sections: list[Section]) -> None:
        results = search_sections("zzzznotfound", sections)
        assert results == []

    def test_max_results_cap(self, sections: list[Section]) -> None:
        results = search_sections("scale", sections, max_results=2)
        assert len(results) <= 2

    def test_heading_weighted_higher(self, sections: list[Section]) -> None:
        results = search_sections("scaleLinear", sections)
        # The section with "scaleLinear" in the heading should rank first
        assert results[0].heading == "scaleLinear"


# --- Module name resolution tests ---


class TestResolveModuleName:
    def test_full_name(self) -> None:
        assert resolve_module_name("d3-scale") == "d3-scale"

    def test_short_name(self) -> None:
        assert resolve_module_name("scale") == "d3-scale"

    def test_case_insensitive(self) -> None:
        assert resolve_module_name("D3-Scale") == "d3-scale"

    def test_unknown(self) -> None:
        assert resolve_module_name("nonexistent") is None

    def test_all_modules_resolvable(self) -> None:
        for m in D3_MODULES:
            assert resolve_module_name(m.name) == m.name


# --- Page path resolution tests ---


class TestResolvePagePath:
    def test_with_leading_slash(self) -> None:
        assert resolve_page_path("/d3-scale/linear") == "/d3-scale/linear"

    def test_without_leading_slash(self) -> None:
        assert resolve_page_path("d3-scale/linear") == "/d3-scale/linear"

    def test_module_index_page(self) -> None:
        assert resolve_page_path("/d3-scale") == "/d3-scale"

    def test_unknown_page(self) -> None:
        assert resolve_page_path("/d3-fake/nope") is None

    def test_all_pages_in_map(self) -> None:
        for m in D3_MODULES:
            for p in m.pages:
                assert p in D3_PAGE_MAP

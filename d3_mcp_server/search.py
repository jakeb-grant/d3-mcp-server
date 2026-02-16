import re

from pydantic import BaseModel

from d3_mcp_server.modules import D3Module

# Split on camelCase boundaries: "scaleLinear" → ["scale", "Linear"]
_CAMEL_RE = re.compile(r"[a-z]+|[A-Z][a-z]*")


def _split_terms(query: str) -> list[str]:
    """Split query into lowercase terms, decomposing camelCase.

    "scaleLinear" → ["scale", "linear", "scalelinear"]
    "bar chart"   → ["bar", "chart"]
    """
    words: list[str] = []
    for token in query.split():
        parts = [p.lower() for p in _CAMEL_RE.findall(token)]
        if len(parts) > 1:
            words.extend(parts)
            words.append(token.lower())
        else:
            words.append(token.lower())
    return words


def score_modules(query: str, modules: list[D3Module]) -> list[tuple[D3Module, int]]:
    """Score modules against a search query.

    Returns (module, score) pairs sorted by score descending.
    Weights: name (10), exact tag (3), description word (2),
    partial tag (1).
    """
    terms = _split_terms(query)
    results: list[tuple[D3Module, int]] = []

    for module in modules:
        score = 0
        name_lower = module.name.lower()
        short_name = name_lower.removeprefix("d3-")
        desc_words = module.description.lower().split()
        tags_lower = [t.lower() for t in module.tags]

        for term in terms:
            if term in (name_lower, short_name):
                score += 10
            if term in tags_lower:
                score += 3
            if term in desc_words:
                score += 2
            if any(term in tag for tag in tags_lower):
                score += 1

        if score > 0:
            results.append((module, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


# HTML anchor pattern used in D3 READMEs for individual API methods
_ANCHOR_RE = re.compile(
    r'<a\s+(?:[^>]*?\s+)?(?:name|id)\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class Section(BaseModel):
    heading: str
    content: str


def parse_sections(markdown: str) -> list[Section]:
    """Parse a D3 README into sections.

    Splits on markdown headings (## or ###) and HTML anchor tags.
    Each section has a heading and the content block until the next.
    """
    lines = markdown.split("\n")
    sections: list[Section] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        # Check for markdown heading (## or ###)
        heading_match = re.match(r"^(#{2,3})\s+(.+)", line)
        # Check for HTML anchor
        anchor_match = _ANCHOR_RE.search(line)

        if heading_match or anchor_match:
            # Save previous section
            if current_heading is not None:
                sections.append(
                    Section(
                        heading=current_heading,
                        content="\n".join(current_lines).strip(),
                    )
                )

            if heading_match:
                current_heading = heading_match.group(2).strip()
            elif anchor_match:
                current_heading = anchor_match.group(1).strip()

            current_lines = [line]
        else:
            current_lines.append(line)

    # Don't forget the last section
    if current_heading is not None:
        sections.append(
            Section(
                heading=current_heading,
                content="\n".join(current_lines).strip(),
            )
        )

    return sections


def search_sections(
    query: str,
    sections: list[Section],
    *,
    max_results: int = 10,
) -> list[Section]:
    """Search parsed sections by matching keywords against heading and content.

    Heading matches weighted 2x. Returns up to max_results sections.
    """
    terms = query.lower().split()
    scored: list[tuple[Section, int]] = []

    for section in sections:
        score = 0
        heading_lower = section.heading.lower()
        content_lower = section.content.lower()

        for term in terms:
            if term in heading_lower:
                score += 2
            if term in content_lower:
                score += 1

        if score > 0:
            scored.append((section, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in scored[:max_results]]

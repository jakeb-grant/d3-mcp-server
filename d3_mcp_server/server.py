from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from d3_mcp_server.cache import fetch_page
from d3_mcp_server.examples import (
    fetch_gallery,
    fetch_notebook,
    score_examples,
)
from d3_mcp_server.modules import (
    D3_MODULE_MAP,
    D3_MODULES,
    resolve_module_name,
    resolve_page_path,
)
from d3_mcp_server.search import (
    parse_sections,
    score_modules,
    search_sections,
)

mcp = FastMCP("D3 Documentation Server")


@mcp.tool
async def find_module(query: str | None = None) -> str:
    """Find D3.js modules by keyword search.

    Without a query, lists all modules. With a query, returns top 5.
    """
    if not query:
        lines = [
            f"- **{m.name}** ({len(m.pages)} pages): {m.description}"
            for m in D3_MODULES
        ]
        return f"Available D3 modules ({len(D3_MODULES)}):\n\n" + "\n".join(lines)

    scored = score_modules(query, D3_MODULES)
    if not scored:
        return f"No modules found matching '{query}'."

    top = scored[:5]
    lines = [f"- **{m.name}** (score {s}): {m.description}" for m, s in top]
    return f"Modules matching '{query}':\n\n" + "\n".join(lines)


@mcp.tool
async def get_docs(
    module_name: str,
    page: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Get D3.js API documentation.

    Provide module_name (e.g. "d3-scale" or "scale") for the overview.
    Add page (e.g. "linear") to get a specific sub-page.
    """
    resolved_name = resolve_module_name(module_name)
    if not resolved_name:
        msg = f"Unknown module '{module_name}'. Use find_module() to list modules."
        raise ToolError(msg)

    module = D3_MODULE_MAP[resolved_name]

    if page:
        page_path = f"/{resolved_name}/{page.strip().lower()}"
        resolved = resolve_page_path(page_path)
        if not resolved:
            available = [p.rsplit("/", 1)[-1] for p in module.pages[1:]]
            msg = (
                f"Unknown page '{page}' for {resolved_name}. "
                f"Available: {', '.join(available)}"
            )
            raise ToolError(msg)
        return await fetch_page(resolved, ctx)

    # Fetch the module's index page
    content = await fetch_page(module.pages[0], ctx)

    if len(module.pages) > 1:
        sub_names = [p.rsplit("/", 1)[-1] for p in module.pages[1:]]
        page_list = "\n".join(f"- `{name}`" for name in sub_names)
        content += (
            f"\n\n---\n\n## Sub-pages\n\n"
            f'Use `get_docs(module_name="{resolved_name}", '
            f"page=...)` for details:\n\n{page_list}"
        )

    return content


@mcp.tool
async def search_docs(
    query: str,
    module_name: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Search D3.js documentation for specific topics or methods.

    Searches page content for matching sections.
    Optionally restrict to a single module with module_name.
    """
    if module_name:
        resolved = resolve_module_name(module_name)
        if not resolved:
            msg = f"Unknown module '{module_name}'. Use find_module() to list modules."
            raise ToolError(msg)
        pages = D3_MODULE_MAP[resolved].pages
    else:
        scored = score_modules(query, D3_MODULES)
        modules = [m for m, _ in scored[:5]]
        pages = [p for m in modules for p in m.pages]

    if not pages:
        return f"No relevant modules found for '{query}'."

    all_results: list[str] = []

    for page_path in pages:
        content = await fetch_page(page_path, ctx)
        sections = parse_sections(content)
        matches = search_sections(query, sections, max_results=3)

        if matches:
            parts = [f"### {s.heading}\n\n{s.content}" for s in matches]
            header = f"## {page_path}\n\n"
            all_results.append(header + "\n\n---\n\n".join(parts))

        if len(all_results) >= 10:
            break

    if not all_results:
        return f"No results for '{query}'."

    return "\n\n---\n\n".join(all_results)


@mcp.tool
async def find_example(
    query: str | None = None,
    category: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Find D3.js examples from the Observable gallery.

    Without arguments, lists all categories with counts.
    With query, returns top 10 matching examples.
    With category, lists examples in that category.
    """
    examples = await fetch_gallery(ctx)

    if not query and not category:
        categories: dict[str, int] = {}
        for ex in examples:
            categories[ex.category] = categories.get(ex.category, 0) + 1
        lines = [f"- **{cat}** ({count})" for cat, count in sorted(categories.items())]
        return (
            f"D3 example categories ({len(categories)}, "
            f"{len(examples)} total examples):\n\n"
            + "\n".join(lines)
            + '\n\nUse `find_example(category="Bars")` to list examples in a category,'
            + ' or `find_example(query="treemap")` to search.'
        )

    if category:
        cat_lower = category.lower()
        filtered = [ex for ex in examples if ex.category.lower() == cat_lower]
        if not filtered:
            cats = sorted({ex.category for ex in examples})
            return f"Unknown category '{category}'. Available: {', '.join(cats)}"
        lines = [f"- **{ex.title}** by {ex.author} — `{ex.path}`" for ex in filtered]
        return (
            f"Examples in '{filtered[0].category}' ({len(filtered)}):\n\n"
            + "\n".join(lines)
        )

    assert query is not None
    scored = score_examples(query, examples)
    if not scored:
        return f"No examples found matching '{query}'."

    top = scored[:10]
    lines = [
        f"- **{ex.title}** [{ex.category}] (score {s}) — `{ex.path}`" for ex, s in top
    ]
    return (
        f"Examples matching '{query}':\n\n"
        + "\n".join(lines)
        + "\n\nUse `get_example(path=...)` to get the source code."
    )


@mcp.tool
async def get_example(
    path: str,
    ctx: Context | None = None,
) -> str:
    """Get D3.js example source code from an Observable notebook.

    Provide the example path (e.g. "@d3/bar-chart/2").
    Use find_example() to discover available examples.
    """
    path = path.strip()
    if not path.startswith("@"):
        path = f"@{path}"

    content = await fetch_notebook(path, ctx)
    return f"## Example: {path}\n\n{content}"


@mcp.resource("d3-docs://{page_path}")
async def doc_page(page_path: str, ctx: Context) -> str:
    """Raw documentation page from d3js.org."""
    resolved = resolve_page_path(page_path)
    if not resolved:
        msg = f"Unknown page '{page_path}'."
        raise ToolError(msg)
    return await fetch_page(resolved, ctx)

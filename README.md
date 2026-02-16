# d3-mcp-server

MCP server that provides D3.js API documentation and example code to AI agents. Fetches docs from [d3js.org](https://d3js.org) and examples from the [Observable D3 gallery](https://observablehq.com/@d3/gallery), serving them through searchable tools.

> **Note:** This project uses [FastMCP](https://gofastmcp.com) 3.0.0rc2, which is an unstable preview release. It will be upgraded to the stable 3.0 release once available.

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

### Claude Code

```bash
claude mcp add -t stdio -s user d3 -- uvx --from git+https://github.com/jakeb-grant/d3-mcp-server d3-mcp-server
```

### Claude Desktop / Cursor / etc.

```json
{
  "mcpServers": {
    "d3": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/jakeb-grant/d3-mcp-server", "d3-mcp-server"]
    }
  }
}
```

### MCP Inspector

```bash
uv run fastmcp dev inspector d3_mcp_server/server.py --with-editable .
```

## Tools

### `find_module(query?)`

Discover D3 modules. Without a query, lists all 30 modules. With a query, returns the top 5 matches ranked by name, tag, and description relevance.

```
find_module()                → list all modules
find_module("scale")         → modules related to scales
find_module("color")         → d3-color, d3-scale-chromatic, d3-interpolate
```

### `get_docs(module_name, page?)`

Fetch documentation for a module. Returns the module overview by default, or a specific sub-page.

```
get_docs("d3-scale")              → scale overview + list of sub-pages
get_docs("scale")                 → same (short names work)
get_docs("d3-scale", "linear")    → linear scales sub-page
get_docs("d3-array", "ticks")     → ticks sub-page
```

### `search_docs(query, module_name?)`

Search documentation content for specific topics or methods. Optionally scope to a single module.

```
search_docs("scaleLinear")              → searches across relevant modules
search_docs("domain", "d3-scale")       → searches within d3-scale only
```

### `find_example(query?, category?)`

Browse and search ~170 D3 examples from the Observable gallery across 14 categories (Bars, Lines, Maps, Hierarchies, etc.).

```
find_example()                    → list all categories with counts
find_example(query="treemap")     → search examples by keyword
find_example(category="Bars")     → list all examples in a category
```

### `get_example(path)`

Fetch example source code from an Observable notebook. Extracts clean, standalone D3 code from the notebook format, along with a description and data file URLs.

```
get_example("@d3/bar-chart/2")           → bar chart source code
get_example("@d3/force-directed-graph/2") → force-directed graph source
```

## Architecture

```
d3_mcp_server/
├── __init__.py    # Entry point (main)
├── server.py      # FastMCP server, tools, resource template
├── modules.py     # D3Module model + 30-module registry
├── examples.py    # Observable gallery scraping + notebook code extraction
├── cache.py       # File cache (~/.cache/d3-mcp-server/) + HTML→markdown
├── search.py      # Module scoring + markdown section parsing/search
└── sync.py        # Registry drift detection (see below)
tests/
├── test_examples.py # Gallery parsing, scoring, notebook extraction tests
├── test_search.py   # Search, parsing, module resolution tests
├── test_cache.py    # HTML conversion, caching, fetch error handling
└── test_server.py   # Tool integration tests
```

Doc pages are fetched from d3js.org, stripped to `<main class="main">` content, converted to markdown via markdownify, and cached to disk with a 24-hour TTL.

## Registry Sync

The module registry in `modules.py` is hardcoded. If d3js.org adds, removes, or renames modules or pages, the registry will drift. A sync utility detects this.

### Check for drift

```bash
uv run python -m d3_mcp_server.sync
```

This scrapes the d3js.org/api sidebar and compares it against the hardcoded `D3_MODULES` list, reporting:

- New modules on d3js.org not in the registry
- Modules in the registry that no longer exist on d3js.org
- New sub-pages added to existing modules
- Sub-pages in the registry that no longer exist on d3js.org

### Updating the registry

When drift is detected, update `d3_mcp_server/modules.py` following these rules:

**`D3_MODULES` is the list to edit.** Each entry is a `D3Module` with:

- `name` — module name exactly as shown on d3js.org (e.g. `"d3-array"`)
- `description` — short summary (copy from the d3js.org sidebar or module index page)
- `tags` — lowercase keywords for search scoring (include the short name, key API terms, and related concepts)
- `pages` — ordered list of page paths; first entry is always the module index page (`"/d3-array"`), followed by sub-pages (`"/d3-array/ticks"`)

**For new modules**, add a `D3Module` entry to `D3_MODULES`. Place it alphabetically among existing entries or group it with related modules. Populate `tags` with the short module name and 3-8 relevant keywords from the module's description and API methods.

**For removed modules**, delete the entire `D3Module` entry.

**For new pages**, append the page path to the module's `pages` list. The path format is `"/{module_name}/{page_slug}"` where the slug matches the d3js.org URL.

**For removed pages**, delete the page path from the module's `pages` list.

After editing, verify:

```bash
uv run python -m d3_mcp_server.sync   # should report no drift
uv run pytest tests/ -v               # all tests should pass
uvx ruff check d3_mcp_server/ tests/  # no lint errors
```

## Development

```bash
uv run pytest tests/ -v                              # run tests
uvx ruff check d3_mcp_server/ tests/                 # lint
uvx ruff format d3_mcp_server/ tests/                # format
uv run python -m d3_mcp_server.sync                  # check registry drift
uv run fastmcp dev inspector d3_mcp_server/server.py --with-editable .  # MCP inspector
```

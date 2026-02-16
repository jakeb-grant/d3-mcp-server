"""Compare hardcoded module registry against live d3js.org sidebar.

Run directly:  uv run python -m d3_mcp_server.sync
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from d3_mcp_server.modules import BASE_URL, D3_MODULE_MAP, D3_MODULES


def fetch_live_registry() -> dict[str, list[str]]:
    """Scrape d3js.org/api sidebar and return {module_name: [pages]}.

    Each module maps to a list of page paths (including its index page).
    """
    response = httpx.get(f"{BASE_URL}/api", timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    nav = soup.find("nav", id="VPSidebarNav")
    if not nav:
        msg = "Could not find sidebar nav on d3js.org/api"
        raise RuntimeError(msg)

    modules: dict[str, list[str]] = {}
    current_module: str | None = None

    for link in nav.find_all("a", href=True):
        href = str(link["href"])
        if not href.startswith("/d3-"):
            continue

        parts = href.strip("/").split("/")
        module_name = parts[0]

        if len(parts) == 1:
            # Module index page
            current_module = module_name
            modules[module_name] = [href]
        elif module_name == current_module:
            # Sub-page of current module
            modules[module_name].append(href)

    return modules


def diff_registry() -> dict[str, list[str]]:
    """Compare live d3js.org registry against hardcoded D3_MODULES.

    Returns a dict of issues keyed by category:
      - "added_modules": modules on d3js.org but not in our registry
      - "removed_modules": modules in our registry but not on d3js.org
      - "added_pages": pages on d3js.org but not in our registry
      - "removed_pages": pages in our registry but not on d3js.org
    """
    live = fetch_live_registry()
    local_names = {m.name for m in D3_MODULES}
    live_names = set(live.keys())

    issues: dict[str, list[str]] = {
        "added_modules": [],
        "removed_modules": [],
        "added_pages": [],
        "removed_pages": [],
    }

    # Modules present on live site but missing locally
    for name in sorted(live_names - local_names):
        pages = ", ".join(live[name])
        issues["added_modules"].append(f"{name} ({pages})")

    # Modules in our registry but gone from live site
    for name in sorted(local_names - live_names):
        issues["removed_modules"].append(name)

    # Page-level diffs for shared modules
    for name in sorted(local_names & live_names):
        local_pages = set(D3_MODULE_MAP[name].pages)
        live_pages = set(live[name])

        for page in sorted(live_pages - local_pages):
            issues["added_pages"].append(f"{name}: {page}")

        for page in sorted(local_pages - live_pages):
            issues["removed_pages"].append(f"{name}: {page}")

    return issues


def print_report() -> None:
    """Print a human-readable drift report."""
    print("Fetching live registry from d3js.org/api...")
    issues = diff_registry()

    total = sum(len(v) for v in issues.values())

    if total == 0:
        print("\nNo drift detected. Registry is up to date.")
        return

    print(f"\nFound {total} difference(s):\n")

    labels = {
        "added_modules": "New modules on d3js.org (not in registry)",
        "removed_modules": "Modules in registry but gone from d3js.org",
        "added_pages": "New pages on d3js.org (not in registry)",
        "removed_pages": "Pages in registry but gone from d3js.org",
    }

    for key, label in labels.items():
        items = issues[key]
        if items:
            print(f"  {label}:")
            for item in items:
                print(f"    - {item}")
            print()


if __name__ == "__main__":
    print_report()

from pydantic import BaseModel

BASE_URL = "https://d3js.org"


class D3Module(BaseModel):
    """A D3.js module with its doc pages on d3js.org."""

    name: str
    description: str
    tags: list[str]
    pages: list[str]

    @property
    def page_urls(self) -> list[str]:
        return [f"{BASE_URL}{p}" for p in self.pages]


D3_MODULES: list[D3Module] = [
    D3Module(
        name="d3-array",
        description="Array manipulation, statistics, searching, and sorting.",
        tags=["array", "statistics", "sort", "bin", "group", "min", "max", "mean"],
        pages=[
            "/d3-array",
            "/d3-array/add",
            "/d3-array/bin",
            "/d3-array/bisect",
            "/d3-array/blur",
            "/d3-array/group",
            "/d3-array/intern",
            "/d3-array/sets",
            "/d3-array/sort",
            "/d3-array/summarize",
            "/d3-array/ticks",
            "/d3-array/transform",
        ],
    ),
    D3Module(
        name="d3-axis",
        description="Human-readable reference marks for scales.",
        tags=["axis", "tick", "scale", "svg"],
        pages=["/d3-axis"],
    ),
    D3Module(
        name="d3-brush",
        description="Select a one- or two-dimensional region using the mouse or touch.",
        tags=["brush", "selection", "interaction", "mouse", "touch"],
        pages=["/d3-brush"],
    ),
    D3Module(
        name="d3-chord",
        description="Chord diagrams visualizing relationships between groups.",
        tags=["chord", "diagram", "ribbon", "relationship", "matrix"],
        pages=[
            "/d3-chord",
            "/d3-chord/chord",
            "/d3-chord/ribbon",
        ],
    ),
    D3Module(
        name="d3-color",
        description="Color spaces including RGB, HSL, Cubehelix, CIELAB.",
        tags=["color", "rgb", "hsl", "lab", "hcl", "cubehelix"],
        pages=["/d3-color"],
    ),
    D3Module(
        name="d3-contour",
        description="Compute contour polygons using marching squares.",
        tags=["contour", "density", "topography", "isoline"],
        pages=[
            "/d3-contour",
            "/d3-contour/contour",
            "/d3-contour/density",
        ],
    ),
    D3Module(
        name="d3-delaunay",
        description="Voronoi diagrams and Delaunay triangulation.",
        tags=["voronoi", "delaunay", "triangulation", "diagram"],
        pages=[
            "/d3-delaunay",
            "/d3-delaunay/delaunay",
            "/d3-delaunay/voronoi",
        ],
    ),
    D3Module(
        name="d3-dispatch",
        description="Register named callbacks and invoke them with arguments.",
        tags=["dispatch", "event", "callback"],
        pages=["/d3-dispatch"],
    ),
    D3Module(
        name="d3-drag",
        description="Drag-and-drop interaction for mouse and touch input.",
        tags=["drag", "interaction", "mouse", "touch"],
        pages=["/d3-drag"],
    ),
    D3Module(
        name="d3-dsv",
        description="Parse and format delimiter-separated values, notably CSV and TSV.",
        tags=["csv", "tsv", "dsv", "parse", "format", "delimiter"],
        pages=["/d3-dsv"],
    ),
    D3Module(
        name="d3-ease",
        description="Easing functions for smooth animation transitions.",
        tags=["ease", "easing", "animation", "transition"],
        pages=["/d3-ease"],
    ),
    D3Module(
        name="d3-fetch",
        description="Convenience methods on top of the Fetch API.",
        tags=["fetch", "csv", "json", "text", "xml", "load"],
        pages=["/d3-fetch"],
    ),
    D3Module(
        name="d3-force",
        description="Force-directed graph layout using velocity Verlet integration.",
        tags=["force", "graph", "layout", "simulation", "network", "collision"],
        pages=[
            "/d3-force",
            "/d3-force/simulation",
            "/d3-force/center",
            "/d3-force/collide",
            "/d3-force/link",
            "/d3-force/many-body",
            "/d3-force/position",
        ],
    ),
    D3Module(
        name="d3-format",
        description="Format numbers for human consumption.",
        tags=["format", "number", "locale", "SI", "currency", "percent"],
        pages=["/d3-format"],
    ),
    D3Module(
        name="d3-geo",
        description="Geographic projections, spherical shapes, and math.",
        tags=["geo", "map", "projection", "geography", "sphere", "graticule"],
        pages=[
            "/d3-geo",
            "/d3-geo/path",
            "/d3-geo/projection",
            "/d3-geo/azimuthal",
            "/d3-geo/conic",
            "/d3-geo/cylindrical",
            "/d3-geo/stream",
            "/d3-geo/shape",
            "/d3-geo/math",
        ],
    ),
    D3Module(
        name="d3-hierarchy",
        description="Layout algorithms for hierarchical data.",
        tags=["hierarchy", "tree", "treemap", "pack", "partition", "cluster"],
        pages=[
            "/d3-hierarchy",
            "/d3-hierarchy/hierarchy",
            "/d3-hierarchy/stratify",
            "/d3-hierarchy/tree",
            "/d3-hierarchy/cluster",
            "/d3-hierarchy/partition",
            "/d3-hierarchy/pack",
            "/d3-hierarchy/treemap",
        ],
    ),
    D3Module(
        name="d3-interpolate",
        description="Interpolate numbers, colors, strings, arrays, and more.",
        tags=["interpolate", "color", "number", "string", "zoom", "tween"],
        pages=[
            "/d3-interpolate",
            "/d3-interpolate/value",
            "/d3-interpolate/color",
            "/d3-interpolate/transform",
            "/d3-interpolate/zoom",
        ],
    ),
    D3Module(
        name="d3-path",
        description="Serialize Canvas path commands to SVG path data.",
        tags=["path", "canvas", "svg", "serialize"],
        pages=["/d3-path"],
    ),
    D3Module(
        name="d3-polygon",
        description="Geometric operations for two-dimensional polygons.",
        tags=["polygon", "hull", "centroid", "area", "convex"],
        pages=["/d3-polygon"],
    ),
    D3Module(
        name="d3-quadtree",
        description="Two-dimensional recursive spatial subdivision.",
        tags=["quadtree", "spatial", "collision", "search"],
        pages=["/d3-quadtree"],
    ),
    D3Module(
        name="d3-random",
        description="Random number generators for various distributions.",
        tags=["random", "distribution", "normal", "uniform", "exponential"],
        pages=["/d3-random"],
    ),
    D3Module(
        name="d3-scale",
        description="Encodings that map abstract data to visual representation.",
        tags=["scale", "linear", "log", "ordinal", "band", "point", "time"],
        pages=[
            "/d3-scale",
            "/d3-scale/linear",
            "/d3-scale/time",
            "/d3-scale/pow",
            "/d3-scale/log",
            "/d3-scale/symlog",
            "/d3-scale/ordinal",
            "/d3-scale/band",
            "/d3-scale/point",
            "/d3-scale/sequential",
            "/d3-scale/diverging",
            "/d3-scale/quantile",
            "/d3-scale/quantize",
            "/d3-scale/threshold",
        ],
    ),
    D3Module(
        name="d3-scale-chromatic",
        description="Sequential, diverging, and categorical color schemes.",
        tags=["color", "scheme", "chromatic", "sequential", "diverging"],
        pages=[
            "/d3-scale-chromatic",
            "/d3-scale-chromatic/categorical",
            "/d3-scale-chromatic/cyclical",
            "/d3-scale-chromatic/diverging",
            "/d3-scale-chromatic/sequential",
        ],
    ),
    D3Module(
        name="d3-selection",
        description="Transform the DOM by selecting elements and binding data.",
        tags=["selection", "dom", "data", "bindattr", "bindstyle", "bindhtml"],
        pages=[
            "/d3-selection",
            "/d3-selection/selecting",
            "/d3-selection/modifying",
            "/d3-selection/joining",
            "/d3-selection/events",
            "/d3-selection/control-flow",
            "/d3-selection/locals",
            "/d3-selection/namespaces",
        ],
    ),
    D3Module(
        name="d3-shape",
        description="Graphical primitives for visualization.",
        tags=["shape", "arc", "pie", "line", "area", "curve", "stack", "symbol"],
        pages=[
            "/d3-shape",
            "/d3-shape/arc",
            "/d3-shape/area",
            "/d3-shape/curve",
            "/d3-shape/line",
            "/d3-shape/link",
            "/d3-shape/pie",
            "/d3-shape/stack",
            "/d3-shape/symbol",
            "/d3-shape/radial-area",
            "/d3-shape/radial-line",
            "/d3-shape/radial-link",
        ],
    ),
    D3Module(
        name="d3-time",
        description="A calculator for humanity's eccentric conventions of time.",
        tags=["time", "interval", "day", "week", "month", "year", "hour"],
        pages=["/d3-time"],
    ),
    D3Module(
        name="d3-time-format",
        description="Parse and format times inspired by strptime and strftime.",
        tags=["time", "format", "parse", "date", "locale", "strftime"],
        pages=["/d3-time-format"],
    ),
    D3Module(
        name="d3-timer",
        description="Efficient queue for managing concurrent animations.",
        tags=["timer", "animation", "interval", "timeout", "frame"],
        pages=["/d3-timer"],
    ),
    D3Module(
        name="d3-transition",
        description="Animated transitions for D3 selections.",
        tags=["transition", "animation", "selection", "tween", "ease"],
        pages=[
            "/d3-transition",
            "/d3-transition/selecting",
            "/d3-transition/modifying",
            "/d3-transition/timing",
            "/d3-transition/control-flow",
        ],
    ),
    D3Module(
        name="d3-zoom",
        description="Pan and zoom SVG, HTML or Canvas using mouse or touch.",
        tags=["zoom", "pan", "interaction", "mouse", "touch", "transform"],
        pages=["/d3-zoom"],
    ),
]

D3_MODULE_MAP: dict[str, D3Module] = {m.name: m for m in D3_MODULES}

# Also index by page path for direct page lookups
D3_PAGE_MAP: dict[str, D3Module] = {}
for _m in D3_MODULES:
    for _p in _m.pages:
        D3_PAGE_MAP[_p] = _m


def resolve_module_name(name: str) -> str | None:
    """Normalize a module name to its canonical form.

    Accepts "d3-scale", "scale", "D3-Scale", etc.
    Returns the canonical name or None if not found.
    """
    name = name.strip().lower()
    if name in D3_MODULE_MAP:
        return name
    prefixed = f"d3-{name}"
    if prefixed in D3_MODULE_MAP:
        return prefixed
    return None


def resolve_page_path(path: str) -> str | None:
    """Resolve a page path like 'd3-scale/linear' or '/d3-scale/linear'.

    Returns the canonical path (with leading /) or None.
    """
    path = path.strip().lower()
    if not path.startswith("/"):
        path = f"/{path}"
    if path in D3_PAGE_MAP:
        return path
    return None

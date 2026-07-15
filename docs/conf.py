"""Documentation generation configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import bump_deps_index
from bump_deps_index import __version__

if TYPE_CHECKING:
    from docutils.nodes import Element, reference
    from sphinx.addnodes import pending_xref
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment


project = name = "bump-deps-index"
now = datetime.now(tz=UTC)
globals()["copyright"] = f"2022-{now.year}"
version, release = __version__, __version__.split("+")[0]

extensions = [
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.inheritance_diagram",
    "sphinx_argparse_cli",
]

master_doc, source_suffix = "index", ".rst"

html_theme = "furo"
html_title, html_last_updated_fmt = "Bump dependencies from package indexes", now.isoformat()
pygments_style, pygments_dark_style = "sphinx", "monokai"

autoclass_content, autodoc_typehints, autodoc_typehints_format = "both", "description", "short"
inheritance_alias, inheritance_graph_attrs = {}, {"rankdir": "TB"}
autodoc_default_options = {"members": True, "member-order": "bysource", "undoc-members": True, "show-inheritance": True}

intersphinx_mapping = {"python": ("https://docs.python.org/3.11", None)}
nitpicky = True
nitpick_ignore = []

for module in (bump_deps_index,):
    for entry in module.__all__:
        to_module = getattr(getattr(module, entry), "__module__", "")
        of = f"{to_module}{'.' if to_module else ''}{entry}"
        if of not in inheritance_alias:  # first instance wins
            inheritance_alias[of] = f"{module.__name__}.{entry}"


def setup(app: Sphinx) -> None:
    """Sphinx resolves pathlib.Path to an undocumented private alias without this hook."""
    app.connect("missing-reference", _resolve_private_path)


def _resolve_private_path(
    app: Sphinx,
    env: BuildEnvironment,
    node: pending_xref,
    contnode: Element,
) -> reference | None:
    if node["reftarget"] != "pathlib._local.Path":
        return None
    node["reftarget"] = "pathlib.Path"
    domain = env.get_domain("py")
    return domain.resolve_xref(env, node["refdoc"], app.builder, node["reftype"], node["reftarget"], node, contnode)

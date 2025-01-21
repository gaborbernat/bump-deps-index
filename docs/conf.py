"""Documentation generation configuration."""  # noqa: INP001

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sphinx.domains.python import PythonDomain

import bump_deps_index
from bump_deps_index import __version__

if TYPE_CHECKING:
    from docutils.nodes import Element
    from sphinx.application import Sphinx
    from sphinx.builders import Builder
    from sphinx.environment import BuildEnvironment


project = name = "bumps-deps-index"
now = datetime.now(tz=UTC)
copyright = f"2022-{now.year}"  # noqa: A001
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
html_title, html_last_updated_fmt = "Bump PyPI deps from index", now.isoformat()
pygments_style, pygments_dark_style = "sphinx", "monokai"

autoclass_content, autodoc_typehints, autodoc_typehints_format = "both", "description", "short"
inheritance_alias, inheritance_graph_attrs = {}, {"rankdir": "TB"}
autodoc_default_options = {"members": True, "member-order": "bysource", "undoc-members": True, "show-inheritance": True}

intersphinx_mapping = {"python": ("https://docs.python.org/3.10", None)}
nitpicky = True
nitpick_ignore = []

for module in (bump_deps_index,):
    for entry in module.__all__:
        to_module = getattr(getattr(module, entry), "__module__", "")
        of = f"{to_module}{'.' if to_module else ''}{entry}"
        if of not in inheritance_alias:  # first instance wins
            inheritance_alias[of] = f"{module.__name__}.{entry}"


def setup(app: Sphinx) -> None:  # noqa: D103
    class PatchedPythonDomain(PythonDomain):
        def resolve_xref(  # noqa: PLR0913,PLR0917
            self,
            env: BuildEnvironment,
            fromdocname: str,
            builder: Builder,
            type: str,  # noqa: A002
            target: str,
            node: resolve_xref,
            contnode: Element,
        ) -> Element:
            # fixup some wrongly resolved mappings
            mapping = {
                "pathlib._local.Path": "pathlib.Path",
            }
            if target in mapping:
                target = node["reftarget"] = mapping[target]
            return super().resolve_xref(env, fromdocname, builder, type, target, node, contnode)

    app.add_domain(PatchedPythonDomain, override=True)

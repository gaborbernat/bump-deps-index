"""Documentation generation configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tomllib import loads
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
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.inheritance_diagram",
    "sphinx_argparse_cli",
]

master_doc, source_suffix = "index", ".rst"
exclude_patterns = ["changelog.d/*"]
autosectionlabel_maxdepth = 2

html_theme = "furo"
html_title, html_last_updated_fmt = "Bump dependencies from package indexes", now.isoformat()
pygments_style, pygments_dark_style = "sphinx", "monokai"

autoclass_content, autodoc_typehints, autodoc_typehints_format = "both", "description", "short"
inheritance_alias, inheritance_graph_attrs = {}, {"rankdir": "TB"}
autodoc_default_options = {"members": True, "member-order": "bysource", "undoc-members": True, "show-inheritance": True}

intersphinx_mapping = {"python": ("https://docs.python.org/3.11", None)}
extlinks = {
    "pr": ("https://github.com/gaborbernat/bump-deps-index/pull/%s", "#%s"),
    "user": ("https://github.com/%s", "@%s"),
}
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
    app.connect("source-read", _include_unreleased)


def _include_unreleased(app: Sphinx, docname: str, source: list[str]) -> None:
    if docname != "changelog":
        return
    root = Path(__file__).parent.parent
    fragments = root / "docs" / "changelog.d"
    app.env.note_dependency(str(fragments))
    sections: list[str] = []
    for category in loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["towncrier"]["type"]:
        entries = [
            f"- {fragment.read_text(encoding='utf-8').strip()}"
            for fragment in sorted(fragments.glob(f"*.{category['directory']}.rst"))
        ]
        if entries:
            sections.extend((
                f".. _release-unreleased-{category['name'].lower().replace(' ', '-')}:",
                "",
                category["name"],
                "~" * len(category["name"]),
                "",
                *entries,
                "",
            ))
    if sections:
        source[0] = source[0].replace(
            ".. towncrier release notes start",
            ".. _release-unreleased:\n\nUnreleased\n----------\n\n"
            + "\n".join(sections)
            + "\n"
            + ".. towncrier release notes start",
        )


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

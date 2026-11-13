from __future__ import annotations

import time
from textwrap import dedent
from typing import TYPE_CHECKING, Final

import pytest
from conftest import index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

_NPM_FOO: Final[dict[str, str]] = {
    "https://npm.example/foo": '{"versions": {"1.0.0": {}, "1.0.5": {}, "1.5.0": {}, "2.0.0": {}}}'
}


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "package.json",
            """
            {
              "dependencies": {"foo": "^1.0.0", "bar": "file:../bar", "baz": "github:a/baz"},
              "devDependencies": {
                "foo": "~1.0.0"
              },
              "peerDependencies": {"foo": "^1.0.0"},
              "scripts": {"foo": "^1.0.0"}
            }
            """,
            """
            {
              "dependencies": {"foo": "^1.5.0", "bar": "file:../bar", "baz": "github:a/baz"},
              "devDependencies": {
                "foo": "~1.0.5"
              },
              "peerDependencies": {"foo": "^1.0.0"},
              "scripts": {"foo": "^1.0.0"}
            }
            """,
            _NPM_FOO,
            id="package-json",
        ),
        pytest.param("package.json", "[]\n", "[]\n", {}, id="package-json-not-an-object"),
        pytest.param(
            "package.json",
            """
            {
              "overrides": {"x": {"dependencies": {"foo": "^1.0.0"}}},
              "description": "a } brace and a \\" quote",
              "dependencies": {"foo": "^1.0.0"}
            }
            """,
            """
            {
              "overrides": {"x": {"dependencies": {"foo": "^1.0.0"}}},
              "description": "a } brace and a \\" quote",
              "dependencies": {"foo": "^1.5.0"}
            }
            """,
            _NPM_FOO,
            id="package-json-top-level-only",
        ),
        pytest.param(
            "package.json",
            """
            {
              "dependencies": {"foo": null, "bar": ["x"]},
              "devDependencies": {"f\\u006fo": "^1.0.0", "baz": {"nested": "^1.0.0"}},
              "optionalDependencies": ["foo"]
            }
            """,
            """
            {
              "dependencies": {"foo": null, "bar": ["x"]},
              "devDependencies": {"f\\u006fo": "^1.5.0", "baz": {"nested": "^1.0.0"}},
              "optionalDependencies": ["foo"]
            }
            """,
            _NPM_FOO,
            id="package-json-escapes-nesting-and-wrong-types",
        ),
        pytest.param(
            "package.json",
            '{"devDependencies": {"foo": "^1.0.0", "bar": "\\u005e2.0.0"}, "devDependencies": {"foo": "^1.0.0"}}\n',
            '{"devDependencies": {"foo": "^1.0.0", "bar": "\\u005e2.0.0"}, "devDependencies": {"foo": "^1.5.0"}}\n',
            _NPM_FOO,
            id="package-json-duplicate-key",
        ),
        pytest.param(
            "package.json",
            '{"dependencies": {"foo": " ^1.0.0 ", "bar": ""}}',
            '{"dependencies": {"foo": "^1.5.0", "bar": ""}}',
            _NPM_FOO,
            id="package-json-padded-and-empty-range",
        ),
    ],
    indirect=["pages"],
)
@pytest.mark.usefixtures("pages")
def test_file_updates(tmp_path: Path, name: str, content: str, expected: str) -> None:
    dest = tmp_path / name
    dest.write_text(dedent(content).lstrip(), encoding="utf-8")

    main(index_args("-f", str(dest)))

    assert dest.read_text(encoding="utf-8") == dedent(expected).lstrip()


_NESTED_DEPENDENCIES: Final[str] = ", ".join(['{"dependencies": {"foo": "^1.0.0"}}'] * 8000)


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "package.json",
            f'{{"x": [{_NESTED_DEPENDENCIES}], "dependencies": {{"foo": "^1.0.0"}}}}',
            f'{{"x": [{_NESTED_DEPENDENCIES}], "dependencies": {{"foo": "^1.5.0"}}}}',
            _NPM_FOO,
            id="package-json-many-nested-objects",
        ),
    ],
    indirect=["pages"],
)
@pytest.mark.usefixtures("pages")
def test_pathological_line_parses_in_linear_time(tmp_path: Path, name: str, content: str, expected: str) -> None:
    dest = tmp_path / name
    dest.write_text(content, encoding="utf-8")
    start = time.perf_counter()

    main(index_args("-f", str(dest)))

    assert (dest.read_text(encoding="utf-8"), time.perf_counter() - start < 1) == (expected, True)

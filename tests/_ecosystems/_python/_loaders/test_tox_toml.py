from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from conftest import PYPI_FOO, Case, index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            Case(
                content="""
            requires = ["A"]
            """,
                pages={"https://pypi.example/simple/a/": "<a>a-1.tar.gz</a>"},
                updates={"A -> A>=1"},
                expected="""
            requires = ["A>=1"]
            """,
            ),
            id="requires",
        ),
        pytest.param(
            Case(
                content="""
            requires = ["A"]

            [env_run_base]
            deps = ["B"]

            [env.test]
            deps = ["-r requirements.txt", "C"]

            [env.no_deps]
            description = "no deps here"

            [ui]
            deps = ["D"]
            """,
                pages={
                    "https://pypi.example/simple/a/": "<a>a-1.tar.gz</a>",
                    "https://pypi.example/simple/b/": "<a>b-2.tar.gz</a>",
                    "https://pypi.example/simple/c/": "<a>c-3.tar.gz</a>",
                    "https://pypi.example/simple/d/": "<a>d-4.tar.gz</a>",
                },
                updates={"A -> A>=1", "B -> B>=2", "C -> C>=3", "D -> D>=4"},
                expected="""
            requires = ["A>=1"]

            [env_run_base]
            deps = ["B>=2"]

            [env.test]
            deps = ["-r requirements.txt", "C>=3"]

            [env.no_deps]
            description = "no deps here"

            [ui]
            deps = ["D>=4"]
            """,
            ),
            id="deps-tables",
        ),
        pytest.param(
            Case(
                content="""
            [env_run_base]
            deps = [
                "pytest>=7.0",
                "coverage>=6.0",
            ]
            """,
                pages={
                    "https://pypi.example/simple/pytest/": "<a>pytest-8.1.tar.gz</a>",
                    "https://pypi.example/simple/coverage/": "<a>coverage-7.1.tar.gz</a>",
                },
                updates={"pytest>=7.0 -> pytest>=8.1", "coverage>=6.0 -> coverage>=7.1"},
                expected="""
            [env_run_base]
            deps = [
                "pytest>=8.1",
                "coverage>=7.1",
            ]
            """,
            ),
            id="multiline-array",
        ),
        pytest.param(
            Case(
                content="""
            requires = ["alpha"]

            [env_run_base]
            deps = [
              { replace = "if", condition = "true", then = ["bravo"], else = ["charlie"], extend = true },
              { replace = "posargs", default = ["delta"], extend = true },
              { replace = "env", name = "X", default = "echo" },
              { replace = "glob", pattern = "*.txt", default = ["foxtrot"], extend = true },
              { replace = "ref", of = ["env_run_base", "deps"] },
            ]

            [env_base.matrix]
            factors = [["py312", "py313"]]
            deps = [
              { replace = "if", condition = "true", then = [
                { replace = "posargs", default = ["golf"], extend = true },
              ], extend = true },
            ]

            [env.type]
            deps = ["hotel"]
            """,
                pages={
                    f"https://pypi.example/simple/{n}/": f"<a>{n}-1.tar.gz</a>"
                    for n in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel")
                },
                updates={
                    f"{n} -> {n}>=1" for n in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel")
                },
                expected="""
            requires = ["alpha>=1"]

            [env_run_base]
            deps = [
              { replace = "if", condition = "true", then = ["bravo>=1"], else = ["charlie>=1"], extend = true },
              { replace = "posargs", default = ["delta>=1"], extend = true },
              { replace = "env", name = "X", default = "echo>=1" },
              { replace = "glob", pattern = "*.txt", default = ["foxtrot>=1"], extend = true },
              { replace = "ref", of = ["env_run_base", "deps"] },
            ]

            [env_base.matrix]
            factors = [["py312", "py313"]]
            deps = [
              { replace = "if", condition = "true", then = [
                { replace = "posargs", default = ["golf>=1"], extend = true },
              ], extend = true },
            ]

            [env.type]
            deps = ["hotel>=1"]
            """,
            ),
            id="substitutions",
        ),
    ],
)
def test_tox_toml_updates_dependencies(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path, case: Case
) -> None:
    for url, page in case.pages.items():
        httpx_mock.add_response(url=url, text=page)
    dest = tmp_path / "tox.toml"
    dest.write_text(dedent(case.content).lstrip())

    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == ("", {"Using Python index: https://pypi.example/simple", *case.updates})
    assert dest.read_text() == dedent(case.expected).lstrip()


def test_tox_toml_malformed_env_entry(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "tox.toml"
    toml = """
    [env]
    broken = "not-a-table"
    """
    dest.write_text(dedent(toml).lstrip())
    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, out) == ("", "")
    assert dest.read_text() == dedent(toml).lstrip()


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "tox.toml",
            """
            [env_run_base]
            deps = [
              "foo>=1",  # see [docs
            ]
            [env_run_base.set_env]
            PINNED = "foo>=1"
            """,
            """
            [env_run_base]
            deps = [
              "foo>=2",  # see [docs
            ]
            [env_run_base.set_env]
            PINNED = "foo>=1"
            """,
            PYPI_FOO,
            id="tox-toml-bracket-in-comment",
        ),
        pytest.param(
            "tox.toml",
            """
            env.test.deps = ["foo>=1"]
            env.test.commands = [["foo>=1"]]
            """,
            """
            env.test.deps = ["foo>=2"]
            env.test.commands = [["foo>=1"]]
            """,
            PYPI_FOO,
            id="tox-toml-dotted-key",
        ),
        pytest.param(
            "tox.toml",
            """
            [env]
            a = { deps = ["foo>=1"], commands = [["foo>=1"]] }
            [env.b]
            deps = ["foo>=1"]
            requires = ["foo>=1"]
            description = \"\"\"
            requires = ["foo>=1"]
            \"\"\"
            [env.b.extra]
            deps = ["foo>=1"]
            """,
            """
            [env]
            a = { deps = ["foo>=2"], commands = [["foo>=1"]] }
            [env.b]
            deps = ["foo>=2"]
            requires = ["foo>=1"]
            description = \"\"\"
            requires = ["foo>=1"]
            \"\"\"
            [env.b.extra]
            deps = ["foo>=1"]
            """,
            PYPI_FOO,
            id="tox-toml-only-paths-the-loader-reads",
        ),
        pytest.param(
            "tox.toml",
            """
            requires = \"\"\"foo>=1\"\"\"
            [[foo]]
            deps = ["foo>=1"]
            [env.a]
            deps = [
              { replace = "ref", of = ["x"], default = "foo>=1" },
              { replace = "posargs", default = ["foo>=1"] },
              { replace = "if", condition = "foo>=1", then = "foo>=1", else = ["foo>=1"] },
            ]
            """,
            """
            requires = \"\"\"foo>=2\"\"\"
            [[foo]]
            deps = ["foo>=1"]
            [env.a]
            deps = [
              { replace = "ref", of = ["x"], default = "foo>=1" },
              { replace = "posargs", default = ["foo>=2"] },
              { replace = "if", condition = "foo>=1", then = "foo>=2", else = ["foo>=2"] },
            ]
            """,
            PYPI_FOO,
            id="tox-toml-substitution-kinds-and-array-tables",
        ),
        pytest.param(
            "tox.toml",
            '[env.deps]\ndeps = ["foo>=1"]\n',
            '[env.deps]\ndeps = ["foo>=2"]\n',
            PYPI_FOO,
            id="tox-toml-env-named-deps",
        ),
        pytest.param(
            "tox.toml",
            """
            [env.a.deps]
            replace = "posargs"
            default = ["foo>=1"]
            [[env.b.deps]]
            replace = "if"
            condition = "env.CI"
            then = ["foo>=1"]
            [[env.b.deps]]
            replace = "env"
            name = "X"
            default = ["foo>=1"]
            """,
            """
            [env.a.deps]
            replace = "posargs"
            default = ["foo>=2"]
            [[env.b.deps]]
            replace = "if"
            condition = "env.CI"
            then = ["foo>=2"]
            [[env.b.deps]]
            replace = "env"
            name = "X"
            default = ["foo>=2"]
            """,
            PYPI_FOO,
            id="tox-toml-replace-in-tables",
        ),
        pytest.param(
            "tox.toml",
            """
            requires = ["foo>=1"]
            [env.a]
            deps = [
              { replace = ["posargs"], default = ["foo>=1"] },
              { replace = { kind = "if" }, then = ["foo>=1"] },
              "foo>=1",
            ]
            """,
            """
            requires = ["foo>=2"]
            [env.a]
            deps = [
              { replace = ["posargs"], default = ["foo>=1"] },
              { replace = { kind = "if" }, then = ["foo>=1"] },
              "foo>=2",
            ]
            """,
            PYPI_FOO,
            id="tox-toml-substitution-kind-not-a-string",
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

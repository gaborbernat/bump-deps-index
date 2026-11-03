from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from conftest import index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@dataclass(frozen=True, slots=True, kw_only=True)
class _Case:
    content: str
    pages: dict[str, str]
    updates: set[str]
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _Case(
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
            _Case(
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
            _Case(
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
            _Case(
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
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path, case: _Case
) -> None:
    for url, page in case.pages.items():
        httpx_mock.add_response(url=url, text=page)
    dest = tmp_path / "tox.toml"
    dest.write_text(dedent(case.content).lstrip())

    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == ("", {"Using Python index: https://pypi.example/simple", *case.updates})
    assert dest.read_text() == dedent(case.expected).lstrip()


@pytest.mark.parametrize(
    ("name", "message"),
    [
        pytest.param("dependencies.json", "{} is not a supported dependency file, so it was skipped", id="unsupported"),
        pytest.param("tox.toml", "{} does not exist; pass a file that exists to --file", id="missing"),
    ],
)
def test_run_rejects_file(capsys: pytest.CaptureFixture[str], tmp_path: Path, name: str, message: str) -> None:
    (tmp_path / "dependencies.json").touch()
    filename = tmp_path / name

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(filename)))

    assert capsys.readouterr().err == f"{message.format(filename)}\n"


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

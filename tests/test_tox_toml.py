from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeIndex


@dataclass(frozen=True, slots=True, kw_only=True)
class _Case:
    content: str
    pypi: dict[str, list[str]]
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
                pypi={"A": ["1"]},
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
                pypi={"A": ["1"], "B": ["2"], "C": ["3"], "D": ["4"]},
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
                pypi={"pytest": ["8.1"], "coverage": ["7.1"]},
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
                pypi={key: ["1"] for key in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel")},
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
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path, case: _Case
) -> None:
    index.pypi.update(case.pypi)
    dest = tmp_path / "tox.toml"
    dest.write_text(dedent(case.content).lstrip())

    assert index.run(dest)

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
def test_run_rejects_file(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path, name: str, message: str
) -> None:
    (tmp_path / "dependencies.json").touch()
    filename = tmp_path / name

    assert not index.run(filename)

    assert capsys.readouterr().err == f"{message.format(filename)}\n"


def test_tox_toml_malformed_env_entry(capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex) -> None:
    dest = tmp_path / "tox.toml"
    toml = """
    [env]
    broken = "not-a-table"
    """
    dest.write_text(dedent(toml).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert (err, out) == ("", "")
    assert dest.read_text() == dedent(toml).lstrip()

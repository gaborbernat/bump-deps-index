from __future__ import annotations

import os
import time
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeIndex
    from pytest_httpx import HTTPXMock


def test_requirements_preserves_comments_and_similar_names(tmp_path: Path, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo  # keep this reason\nfoobar\n", encoding="utf-8")
    index.pypi["foo"] = ["2"]
    index.pypi["foobar"] = ["3"]

    assert index.run(requirements)

    assert requirements.read_text(encoding="utf-8") == "foo>=2  # keep this reason\nfoobar>=3\n"


def test_pyproject_updates_only_dependency_tables(tmp_path: Path, index: FakeIndex) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        dedent(
            """
            [project]
            name = "example"

            [project.optional-dependencies]
            test = ["foo"]

            [tool.example]
            dependencies = ["foo"]
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi["foo"] = ["2"]

    assert index.run(pyproject)

    assert '[project.optional-dependencies]\ntest = ["foo>=2"]' in pyproject.read_text(encoding="utf-8")
    assert '[tool.example]\ndependencies = ["foo"]' in pyproject.read_text(encoding="utf-8")


def test_setup_cfg_updates_only_requirement_values(tmp_path: Path, index: FakeIndex) -> None:
    setup_cfg = tmp_path / "setup.cfg"
    setup_cfg.write_text(
        dedent(
            """
            [options]
            packages = foo
            python_requires = >=3.11
            install_requires =
                foo
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi["foo"] = ["2"]

    assert index.run(setup_cfg)

    assert (
        setup_cfg.read_text(encoding="utf-8")
        == dedent(
            """
        [options]
        packages = foo
        python_requires = >=3.11
        install_requires =
            foo>=2
        """
        ).lstrip()
    )


def test_tox_ini_preserves_commands_and_factors(tmp_path: Path, index: FakeIndex) -> None:
    tox_ini = tmp_path / "tox.ini"
    tox_ini.write_text(
        dedent(
            """
            [testenv]
            deps =
                py311: foo
            commands = foo
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi["foo"] = ["2"]

    assert index.run(tox_ini)

    assert (
        tox_ini.read_text(encoding="utf-8")
        == dedent(
            """
        [testenv]
        deps =
            py311: foo>=2
        commands = foo
        """
        ).lstrip()
    )


def test_pre_commit_preserves_repository_urls(tmp_path: Path, index: FakeIndex) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        dedent(
            """
            repos:
              - repo: https://example.com/foo
                hooks:
                  - id: foo
                    additional_dependencies:
                      - foo
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi["foo"] = ["2"]

    assert index.run(config)

    assert "repo: https://example.com/foo" in config.read_text(encoding="utf-8")
    assert "      - foo>=2" in config.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        pytest.param(
            "tox.ini",
            """
            [tox]
            requires = foo
            [testenv]
            deps = foo>=1  # why
            [testenv:url]
            deps =
                bar @ git+https://github.com/a/bar
                py311, !pypy: foo>=1
            """,
            """
            [tox]
            requires = foo>=2
            [testenv]
            deps = foo>=2  # why
            [testenv:url]
            deps =
                bar @ git+https://github.com/a/bar
                py311, !pypy: foo>=2
            """,
            id="tox-ini-single-line-and-url",
        ),
        pytest.param(
            "setup.cfg",
            """
            [options]
            install_requires = foo>=1
            [options.extras_require]
            test = foo
            """,
            """
            [options]
            install_requires = foo>=2
            [options.extras_require]
            test = foo>=2
            """,
            id="setup-cfg-single-line",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            optional-dependencies = { test = ["foo>=1"] }
            """,
            """
            [project]
            name = "demo"
            optional-dependencies = { test = ["foo>=2"] }
            """,
            id="pyproject-inline-table",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "my-pkg"
            dependencies = ["My_Pkg[x]>=1", "foo>=1"]
            """,
            """
            [project]
            name = "my-pkg"
            dependencies = ["My_Pkg[x]>=1", "foo>=2"]
            """,
            id="pyproject-skips-own-non-canonical-name",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = [
              "foo>=1",  # see [docs
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            dependencies = [
              "foo>=2",  # see [docs
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            id="pyproject-bracket-in-comment",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = ["  foo>=1 "]
            """,
            """
            [project]
            name = "demo"
            dependencies = ["  foo>=2 "]
            """,
            id="pyproject-padded-spec",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = [
              "not \\"]\\" valid",
              "foo>=1",
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            dependencies = [
              "not \\"]\\" valid",
              "foo>=2",
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            id="pyproject-bracket-in-string",
        ),
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
            id="tox-toml-bracket-in-comment",
        ),
    ],
)
@pytest.mark.usefixtures("foo_index")
def test_file_updates(tmp_path: Path, index: FakeIndex, name: str, content: str, expected: str) -> None:
    dest = tmp_path / name
    dest.write_text(dedent(content).lstrip(), encoding="utf-8")

    assert index.run(dest)

    assert dest.read_text(encoding="utf-8") == dedent(expected).lstrip()


@pytest.mark.usefixtures("foo_index")
def test_requirements_preserves_crlf_line_endings(tmp_path: Path, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_bytes(b"foo>=1\r\nbar>=1\r\n")
    index.pypi["bar"] = ["1"]

    assert index.run(requirements)

    assert requirements.read_bytes() == b"foo>=2\r\nbar>=1\r\n"


@pytest.mark.usefixtures("foo_index")
def test_unchanged_file_is_not_rewritten(tmp_path: Path, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo>=2\n", encoding="utf-8")
    os.utime(requirements, ns=(0, 0))

    assert index.run(requirements)

    assert requirements.stat().st_mtime_ns == 0


@pytest.mark.usefixtures("foo_index")
def test_package_shared_across_files_is_fetched_once(tmp_path: Path, httpx_mock: HTTPXMock, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo>=1\n", encoding="utf-8")
    tox_toml = tmp_path / "tox.toml"
    tox_toml.write_text('[env_run_base]\ndeps = ["foo>=1", "foo>=1.5"]\n', encoding="utf-8")

    assert index.run(requirements, tox_toml)

    assert (requirements.read_text(encoding="utf-8"), tox_toml.read_text(encoding="utf-8")) == (
        "foo>=2\n",
        '[env_run_base]\ndeps = ["foo>=2", "foo>=2"]\n',
    )
    assert len(httpx_mock.get_requests()) == 1


def test_requires_python_comes_from_nearest_pyproject(tmp_path: Path, index: FakeIndex) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.9"\n')
    (tmp_path / "requirements").mkdir()
    requirements = tmp_path / "requirements" / "requirements-dev.txt"
    requirements.write_text("foo\n", encoding="utf-8")
    index.pypi["foo"] = ["1", "2"]
    index.requires_python["foo-2.tar.gz"] = ">=3.10"

    assert index.run(requirements)

    assert requirements.read_text(encoding="utf-8") == "foo>=1\n"


def test_failure_message_redacts_index_credentials(
    tmp_path: Path, index: FakeIndex, capsys: pytest.CaptureFixture[str]
) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo\n", encoding="utf-8")
    index.index_url = "https://user:s3cret@pypi.example/simple"

    assert not index.run(requirements)

    err = capsys.readouterr().err
    assert "https://pypi.example/simple/foo/" in err
    assert "s3cret" not in err


def test_output_redacts_direct_reference_credentials(
    tmp_path: Path, index: FakeIndex, capsys: pytest.CaptureFixture[str]
) -> None:
    requirements = tmp_path / "requirements.txt"
    content = "foo @ https://user:s3cret@files.example/foo-1.0-py3-none-any.whl\n"
    requirements.write_text(content, encoding="utf-8")

    assert index.run(requirements)

    assert (capsys.readouterr().out.splitlines(), requirements.read_text(encoding="utf-8")) == (
        ["Using Python index: https://pypi.example/simple", "foo @ https://files.example/foo-1.0-py3-none-any.whl"],
        content,
    )


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        pytest.param(
            "tox.ini",
            f"[testenv]\ndeps =\n    {'!,' * 26}x\n    foo>=1\n",
            f"[testenv]\ndeps =\n    {'!,' * 26}x\n    foo>=2\n",
            id="tox-ini-factor-like-commas",
        ),
        pytest.param(
            "pyproject.toml",
            f'[project]\nname = "demo"\ndependencies = [\n  "foo"{" " * 100_000},\n]\n',
            f'[project]\nname = "demo"\ndependencies = [\n  "foo>=2"{" " * 100_000},\n]\n',
            id="pyproject-long-whitespace",
        ),
    ],
)
@pytest.mark.usefixtures("foo_index")
def test_pathological_line_parses_in_linear_time(
    tmp_path: Path, index: FakeIndex, name: str, content: str, expected: str
) -> None:
    dest = tmp_path / name
    dest.write_text(content, encoding="utf-8")
    start = time.perf_counter()

    assert index.run(dest)

    assert (dest.read_text(encoding="utf-8"), time.perf_counter() - start < 1) == (expected, True)


@pytest.fixture
def foo_index(index: FakeIndex) -> None:
    index.pypi["foo"] = ["2"]

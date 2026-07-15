from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from bump_deps_index._cli import Options
from bump_deps_index._run import run

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


def test_requirements_preserves_comments_and_similar_names(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo  # keep this reason\nfoobar\n", encoding="utf-8")
    httpx_mock.add_response(url="https://index.example/simple/foo/", text="<a>foo-2.tar.gz</a>")
    httpx_mock.add_response(url="https://index.example/simple/foobar/", text="<a>foobar-3.tar.gz</a>")

    run(
        Options(
            index_url="https://index.example/simple",
            npm_registry="https://registry.example",
            pkgs=[],
            filenames=[requirements],
            pre_release="no",
        )
    )

    assert requirements.read_text(encoding="utf-8") == "foo>=2  # keep this reason\nfoobar>=3\n"


def test_pyproject_updates_only_dependency_tables(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
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
    httpx_mock.add_response(url="https://index.example/simple/foo/", text="<a>foo-2.tar.gz</a>")

    run(
        Options(
            index_url="https://index.example/simple",
            npm_registry="https://registry.example",
            pkgs=[],
            filenames=[pyproject],
            pre_release="no",
        )
    )

    assert '[project.optional-dependencies]\ntest = ["foo>=2"]' in pyproject.read_text(encoding="utf-8")
    assert '[tool.example]\ndependencies = ["foo"]' in pyproject.read_text(encoding="utf-8")


def test_setup_cfg_updates_only_requirement_values(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
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
    httpx_mock.add_response(url="https://index.example/simple/foo/", text="<a>foo-2.tar.gz</a>")

    run(
        Options(
            index_url="https://index.example/simple",
            npm_registry="https://registry.example",
            pkgs=[],
            filenames=[setup_cfg],
            pre_release="no",
        )
    )

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


def test_tox_ini_preserves_commands_and_factors(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
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
    httpx_mock.add_response(url="https://index.example/simple/foo/", text="<a>foo-2.tar.gz</a>")

    run(
        Options(
            index_url="https://index.example/simple",
            npm_registry="https://registry.example",
            pkgs=[],
            filenames=[tox_ini],
            pre_release="no",
        )
    )

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


def test_pre_commit_preserves_repository_urls(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
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
    httpx_mock.add_response(url="https://index.example/simple/foo/", text="<a>foo-2.tar.gz</a>")

    run(
        Options(
            index_url="https://index.example/simple",
            npm_registry="https://registry.example",
            pkgs=[],
            filenames=[config],
            pre_release="no",
        )
    )

    assert "repo: https://example.com/foo" in config.read_text(encoding="utf-8")
    assert "      - foo>=2" in config.read_text(encoding="utf-8")

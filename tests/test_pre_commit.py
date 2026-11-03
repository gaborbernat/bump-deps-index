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


def test_run_pre_commit(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        url="https://pypi.example/simple/black/", text="<a>black-22.6.0.tar.gz</a><a>black-22.8.0.tar.gz</a>"
    )
    httpx_mock.add_response(
        url="https://pypi.example/simple/flake8-bugbear/",
        text="<a>flake8-bugbear-22.7.1.tar.gz</a><a>flake8-bugbear-22.7.2.tar.gz</a>",
    )
    httpx_mock.add_response(url="https://npm.example/prettier", json={"versions": {"2.7.0": {}, "2.8.0": {}}})
    dest = tmp_path / ".pre-commit-config.yaml"
    content = """
    repos:
      - repo: https://github.com/asottile/blacken-docs
        hooks:
          - id: blacken-docs
            additional_dependencies:
            - black==22.6.0
            - prettier@2.7.0
      - repo: https://github.com/PyCQA/flake8
        hooks:
          - id: flake8
            additional_dependencies:
            - flake8-bugbear==22.7.1
    """
    dest.write_text(dedent(content).lstrip())

    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == (
        "",
        {
            "Using Python index: https://pypi.example/simple",
            "Using JavaScript index: https://npm.example",
            "black==22.6.0 -> black==22.8",
            "flake8-bugbear==22.7.1 -> flake8-bugbear==22.7.2",
            "prettier@2.7.0 -> prettier@2.8.0",
        },
    )

    expected = """
    repos:
      - repo: https://github.com/asottile/blacken-docs
        hooks:
          - id: blacken-docs
            additional_dependencies:
            - black==22.8
            - prettier@2.8.0
      - repo: https://github.com/PyCQA/flake8
        hooks:
          - id: flake8
            additional_dependencies:
            - flake8-bugbear==22.7.2
    """
    assert dest.read_text() == dedent(expected).lstrip()


@dataclass(frozen=True, slots=True, kw_only=True)
class _Case:
    pages: dict[str, str]
    content: str
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _Case(
                pages={
                    "https://pypi.example/simple/bar/": "<a>bar-2.tar.gz</a>",
                    "https://pypi.example/simple/baz/": "<a>baz-3.tar.gz</a>",
                    "https://pypi.example/simple/foo/": "<a>foo-1.tar.gz</a>",
                },
                content="""
            repos:
              - repo: local
                hooks:
                  - id: example
                    additional_dependencies: [foo, "bar"]
                  - id: comments
                    additional_dependencies:
                      - baz  # keep this reason
            """,
                expected="""
            repos:
              - repo: local
                hooks:
                  - id: example
                    additional_dependencies: [foo>=1, "bar>=2"]
                  - id: comments
                    additional_dependencies:
                      - baz>=3  # keep this reason
            """,
            ),
            id="preserves-yaml-layout",
        ),
        pytest.param(
            _Case(
                pages={"https://pypi.example/simple/black/": "<a>black-24.1.tar.gz</a>"},
                content="""
            repos:
              - repo: local
                hooks:
                  - id: go
                    language: golang
                    additional_dependencies: [github.com/a/b@v1.0.0]
                  - id: rust
                    language: rust
                    additional_dependencies: ["cli:ripgrep:14.0.0"]
                  - id: py
                    language: python
                    additional_dependencies: [black]
            """,
                expected="""
            repos:
              - repo: local
                hooks:
                  - id: go
                    language: golang
                    additional_dependencies: [github.com/a/b@v1.0.0]
                  - id: rust
                    language: rust
                    additional_dependencies: ["cli:ripgrep:14.0.0"]
                  - id: py
                    language: python
                    additional_dependencies: [black>=24.1]
            """,
            ),
            id="follows-hook-language",
        ),
        pytest.param(
            _Case(
                pages={"https://npm.example/eslint": '{"versions": {"9.0.0": {}}}'},
                content="""
            repos:
              - repo: local
                hooks:
                  - id: lint
                    language: node
                    additional_dependencies: [eslint]
            """,
                expected="""
            repos:
              - repo: local
                hooks:
                  - id: lint
                    language: node
                    additional_dependencies: [eslint@9.0.0]
            """,
            ),
            id="node-hook-dependencies-are-javascript",
        ),
    ],
)
def test_run_pre_commit_updates_dependencies(httpx_mock: HTTPXMock, tmp_path: Path, case: _Case) -> None:
    for url, page in case.pages.items():
        httpx_mock.add_response(url=url, text=page)
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(dedent(case.content).lstrip(), encoding="utf-8")

    main(index_args("-f", str(config)))

    assert config.read_text(encoding="utf-8") == dedent(case.expected).lstrip()


def test_run_pre_commit_keeps_filtered_inline_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "foo"\n', encoding="utf-8")
    config = tmp_path / ".pre-commit-config.yaml"
    content = "repos:\n  - repo: local\n    hooks:\n      - id: foo\n        additional_dependencies: [foo]\n"
    config.write_text(content, encoding="utf-8")

    main(index_args("-f", str(config)))

    assert config.read_text(encoding="utf-8") == content


def test_run_args_empty(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f"))

    assert capsys.readouterr() == (
        "",
        "no supported dependency files found in the working directory; pass --file or packages\n",
    )


def test_run_pre_commit_reports_missing_npm_package(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(url="https://npm.example/nope", status_code=404)
    config = tmp_path / ".pre-commit-config.yaml"
    content = """
    repos:
      - repo: local
        hooks:
          - id: lint
            language: node
            additional_dependencies: [nope]
    """
    config.write_text(dedent(content).lstrip(), encoding="utf-8")

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(config)))

    assert capsys.readouterr().err.startswith("failed to look up nope, so it was not updated: HTTPStatusError(")
    assert config.read_text() == dedent(content).lstrip()


def test_run_pre_commit_reads_remote_hook_language(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/black/", text="<a>black-24.1.tar.gz</a>")
    httpx_mock.add_response(url="https://npm.example/eslint", json={"versions": {"9.0.0": {}}})
    httpx_mock.add_response(
        url="https://raw.githubusercontent.com/a/hooks/v1.0/.pre-commit-hooks.yaml",
        text="- id: go\n  language: golang\n- id: lint\n  language: node\n- not a hook\n",
    )
    httpx_mock.add_response(url="https://gitlab.com/b/hooks/-/raw/v2/.pre-commit-hooks.yaml", status_code=404)
    httpx_mock.add_response(url="https://raw.githubusercontent.com/c/hooks/v3/.pre-commit-hooks.yaml", text="[invalid")
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        dedent(
            """
            repos:
              - repo: https://github.com/a/hooks.git
                rev: v1.0
                hooks:
                  - id: go
                    additional_dependencies: [black]
                  - id: lint
                    # additional_dependencies: [black]
                    additional_dependencies: [eslint]
              - repo: https://gitlab.com/b/hooks
                rev: v2
                hooks: [{id: missing-manifest, additional_dependencies: [black]}]
              - repo: https://github.com/c/hooks
                rev: v3
                hooks: [{id: invalid-manifest, additional_dependencies: [black]}]
              - repo: https://codeberg.org/d/hooks
                rev: v4
                hooks: [{id: other-host, additional_dependencies: [black], args: [black]}]
              - repo: https://github.com/e/hooks
                hooks: [{id: unpinned, additional_dependencies: [black]}]
            """
        ).lstrip(),
        encoding="utf-8",
    )

    main(index_args("-f", str(config)))

    assert (
        config.read_text(encoding="utf-8")
        == dedent(
            """
        repos:
          - repo: https://github.com/a/hooks.git
            rev: v1.0
            hooks:
              - id: go
                additional_dependencies: [black]
              - id: lint
                # additional_dependencies: [black]
                additional_dependencies: [eslint@9.0.0]
          - repo: https://gitlab.com/b/hooks
            rev: v2
            hooks: [{id: missing-manifest, additional_dependencies: [black>=24.1]}]
          - repo: https://github.com/c/hooks
            rev: v3
            hooks: [{id: invalid-manifest, additional_dependencies: [black>=24.1]}]
          - repo: https://codeberg.org/d/hooks
            rev: v4
            hooks: [{id: other-host, additional_dependencies: [black>=24.1], args: [black]}]
          - repo: https://github.com/e/hooks
            hooks: [{id: unpinned, additional_dependencies: [black>=24.1]}]
        """
        ).lstrip()
    )

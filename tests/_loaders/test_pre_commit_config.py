from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from conftest import PYPI_FOO, Case, index_args

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


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            Case(
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
                updates=set(),
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
            Case(
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
                updates=set(),
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
            Case(
                pages={"https://npm.example/eslint": '{"versions": {"9.0.0": {}}}'},
                content="""
            repos:
              - repo: local
                hooks:
                  - id: lint
                    language: node
                    additional_dependencies: [eslint]
            """,
                updates=set(),
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
def test_run_pre_commit_updates_dependencies(httpx_mock: HTTPXMock, tmp_path: Path, case: Case) -> None:
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


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - additional_dependencies:
                      - foo>=1
                    id: block
                  - additional_dependencies: [foo>=1]
                    id: flow
                  - id: other
                    args: [foo>=1]
            """,
            """
            repos:
              - repo: local
                hooks:
                  - additional_dependencies:
                      - foo>=2
                    id: block
                  - additional_dependencies: [foo>=2]
                    id: flow
                  - id: other
                    args: [foo>=1]
            """,
            PYPI_FOO,
            id="pre-commit-dependencies-first-key",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - id: lint
                    additional_dependencies: [
                      "foo>=1",
                      foo>=1,  # why
                      foo>=1
                    ]
                    args: [foo>=1]
            """,
            """
            repos:
              - repo: local
                hooks:
                  - id: lint
                    additional_dependencies: [
                      "foo>=2",
                      foo>=2,  # why
                      foo>=2
                    ]
                    args: [foo>=1]
            """,
            PYPI_FOO,
            id="pre-commit-multi-line-flow",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - id: g
                    entry: "echo additional_dependencies: x"
                    language: golang
                    additional_dependencies: [foo>=1]
                  - id: py
                    language: python
                    additional_dependencies:
                      [foo>=1, "foo>=1",  # not, foo>=1
                       foo>=1]
            """,
            """
            repos:
              - repo: local
                hooks:
                  - id: g
                    entry: "echo additional_dependencies: x"
                    language: golang
                    additional_dependencies: [foo>=1]
                  - id: py
                    language: python
                    additional_dependencies:
                      [foo>=2, "foo>=2",  # not, foo>=1
                       foo>=2]
            """,
            PYPI_FOO,
            id="pre-commit-key-in-value-and-flow-on-next-line",
        ),
        pytest.param(".pre-commit-config.yaml", "repos:\n", "repos:\n", {}, id="pre-commit-null-repos"),
        pytest.param(
            ".pre-commit-config.yaml",
            "repos:\n  - repo: local\n  - 1\n  - repo: local\n    hooks: [{id: x, additional_dependencies: [1]}]\n",
            "repos:\n  - repo: local\n  - 1\n  - repo: local\n    hooks: [{id: x, additional_dependencies: [1]}]\n",
            {},
            id="pre-commit-repo-without-hooks",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - id: a
                    language: python
                    "additional_dependencies": ["foo>=1; python_version>\\"3\\"", 'foo>=1; os_name==''nt''']
                  - id: g
                    language: golang
                    entry: |
                      additional_dependencies: [foo>=1]
                    additional_dependencies: ["foo @ https://h/x[y.whl", foo>=1]
                  - id: b
                    language: python
                    additional_dependencies:
                      - foo>=1
            #     - old>=1
                      - "x, foo>=1 #y"
                      - foo>=1
            """,
            """
            repos:
              - repo: local
                hooks:
                  - id: a
                    language: python
                    "additional_dependencies": ["foo>=2; python_version>\\"3\\"", 'foo>=2; os_name==''nt''']
                  - id: g
                    language: golang
                    entry: |
                      additional_dependencies: [foo>=1]
                    additional_dependencies: ["foo @ https://h/x[y.whl", foo>=1]
                  - id: b
                    language: python
                    additional_dependencies:
                      - foo>=2
            #     - old>=1
                      - "x, foo>=1 #y"
                      - foo>=2
            """,
            PYPI_FOO,
            id="pre-commit-yaml-nodes",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            base: &base {language: golang, additional_dependencies: [foo>=1]}
            repos:
              - repo: local
                hooks:
                  - <<: *base
                    id: merged
                  - id: a
                    language: python
                    additional_dependencies: [&pin foo>=1, !!str "foo>=1"]
                  - id: b
                    language: [python]
                    additional_dependencies: [*pin]
                  - id: c
                    language: python
                    additional_dependencies:
                      - foo
                        >=1
                      - &d # pinned
                        foo>=1
                  - <<: *base
                    <<: {language: python, additional_dependencies: [foo>=1]}
                    id: last-merge
            """,
            """
            base: &base {language: golang, additional_dependencies: [foo>=1]}
            repos:
              - repo: local
                hooks:
                  - <<: *base
                    id: merged
                  - id: a
                    language: python
                    additional_dependencies: [&pin foo>=2, !!str "foo>=2"]
                  - id: b
                    language: [python]
                    additional_dependencies: [*pin]
                  - id: c
                    language: python
                    additional_dependencies:
                      - foo >=2
                      - &d # pinned
                        foo>=2
                  - <<: *base
                    <<: {language: python, additional_dependencies: [foo>=2]}
                    id: last-merge
            """,
            PYPI_FOO,
            id="pre-commit-anchors-tags-merge-keys-and-folded-scalars",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - id: a
                    language: python
                    additional_dependencies: [foo<3, foo, 'foo<4']
            """,
            """
            repos:
              - repo: local
                hooks:
                  - id: a
                    language: python
                    additional_dependencies: ["foo<3,>=2", foo>=2, 'foo<4,>=2']
            """,
            PYPI_FOO,
            id="pre-commit-flow-sequence-quotes-comma",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - id: a
                    language: node
                    additional_dependencies: [" ", bar@1.0.0]
            """,
            """
            repos:
              - repo: local
                hooks:
                  - id: a
                    language: node
                    additional_dependencies: [" ", bar@2.0.0]
            """,
            {"https://npm.example/bar": '{"versions": {"2.0.0": {}}}'},
            id="pre-commit-blank-dependency",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: https://example.com/foo
                hooks:
                  - id: foo
                    additional_dependencies:
                      - foo
            """,
            """
            repos:
              - repo: https://example.com/foo
                hooks:
                  - id: foo
                    additional_dependencies:
                      - foo>=2
            """,
            PYPI_FOO,
            id="pre-commit-preserves-repository-urls",
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

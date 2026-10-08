from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import httpx
from conftest import FakeIndex

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_httpx import HTTPXMock


def test_run_pre_commit(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update({"black": ["22.6.0", "22.8.0"], "flake8-bugbear": ["22.7.1", "22.7.2"]})
    index.npm["prettier"] = ["2.7.0", "2.8.0"]
    dest = tmp_path / ".pre-commit-config.yaml"
    setup_cfg = """
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
    dest.write_text(dedent(setup_cfg).lstrip())

    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "Using JavaScript index: https://npm.example",
        "black==22.6.0 -> black==22.8",
        "flake8-bugbear==22.7.1 -> flake8-bugbear==22.7.2",
        "prettier@2.7.0 -> prettier@2.8.0",
    }

    setup_cfg = """
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
    assert dest.read_text() == dedent(setup_cfg).lstrip()


def test_run_pre_commit_preserves_yaml_layout(index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update(bar=["2"], baz=["3"], foo=["1"])
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        dedent(
            """
            repos:
              - repo: local
                hooks:
                  - id: example
                    additional_dependencies: [foo, "bar"]
                  - id: comments
                    additional_dependencies:
                      - baz  # keep this reason
            """
        ).lstrip(),
        encoding="utf-8",
    )

    assert index.run(config)

    assert (
        config.read_text(encoding="utf-8")
        == dedent(
            """
        repos:
          - repo: local
            hooks:
              - id: example
                additional_dependencies: [foo>=1, "bar>=2"]
              - id: comments
                additional_dependencies:
                  - baz>=3  # keep this reason
        """
        ).lstrip()
    )


def test_run_pre_commit_keeps_filtered_inline_dependencies(
    index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "foo"\n', encoding="utf-8")
    config = tmp_path / ".pre-commit-config.yaml"
    content = "repos:\n  - repo: local\n    hooks:\n      - id: foo\n        additional_dependencies: [foo]\n"
    config.write_text(content, encoding="utf-8")

    assert index.run(config)

    assert config.read_text(encoding="utf-8") == content


def test_run_args_empty(capsys: pytest.CaptureFixture[str], index: FakeIndex) -> None:
    assert not index.run()

    assert capsys.readouterr() == ("", "no supported dependency files found\n")


def test_run_pre_commit_node_hook_dependencies_are_javascript(index: FakeIndex, tmp_path: Path) -> None:
    index.npm["eslint"] = ["9.0.0"]
    config = tmp_path / ".pre-commit-config.yaml"
    content = """
    repos:
      - repo: local
        hooks:
          - id: lint
            language: node
            additional_dependencies: [eslint]
    """
    config.write_text(dedent(content).lstrip(), encoding="utf-8")

    assert index.run(config)

    assert config.read_text(encoding="utf-8") == dedent(content).lstrip().replace("[eslint]", "[eslint@9.0.0]")


def test_run_pre_commit_reports_missing_npm_package(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path
) -> None:
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

    assert not index.run(config)

    assert capsys.readouterr().err.startswith("failed nope with HTTPStatusError(")
    assert config.read_text() == dedent(content).lstrip()


def test_run_pre_commit_follows_hook_language(index: FakeIndex, tmp_path: Path) -> None:
    index.pypi["black"] = ["24.1"]
    config = tmp_path / ".pre-commit-config.yaml"
    content = """
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
    """
    config.write_text(dedent(content).lstrip(), encoding="utf-8")

    assert index.run(config)

    assert config.read_text(encoding="utf-8") == dedent(content).lstrip().replace("[black]", "[black>=24.1]")


def test_run_pre_commit_reads_remote_hook_language(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    fake = FakeIndex(pypi={"black": ["24.1"]}, npm={"eslint": ["9.0.0"]})
    manifests = {
        "https://raw.githubusercontent.com/a/hooks/v1.0/.pre-commit-hooks.yaml": httpx.Response(
            200, text="- id: go\n  language: golang\n- id: lint\n  language: node\n- not a hook\n"
        ),
        "https://gitlab.com/b/hooks/-/raw/v2/.pre-commit-hooks.yaml": httpx.Response(404),
        "https://raw.githubusercontent.com/c/hooks/v3/.pre-commit-hooks.yaml": httpx.Response(200, text="[invalid"),
    }
    httpx_mock.add_callback(lambda request: manifests.get(str(request.url)) or fake.serve(request), is_reusable=True)
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

    assert fake.run(config)

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

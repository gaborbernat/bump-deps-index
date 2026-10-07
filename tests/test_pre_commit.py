from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from bump_deps_index import Options, run

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from conftest import FakeIndex


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


def test_run_pre_commit_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / ".pre-commit-config.yaml"
    dest.write_text("")
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()


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


def test_run_pre_commit_keeps_filtered_inline_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "foo"\n', encoding="utf-8")
    config = tmp_path / ".pre-commit-config.yaml"
    content = "repos:\n  - repo: local\n    hooks:\n      - id: foo\n        additional_dependencies: [foo]\n"
    config.write_text(content, encoding="utf-8")

    successful = run(Options(index_url="I", npm_registry="N", pkgs=[], filenames=[config], pre_release="no"))

    assert successful
    assert config.read_text(encoding="utf-8") == content


def test_run_args_empty(capsys: pytest.CaptureFixture[str], index: FakeIndex) -> None:
    assert index.run()

    out, err = capsys.readouterr()
    assert err == "no supported dependency files found\n"
    assert not out


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

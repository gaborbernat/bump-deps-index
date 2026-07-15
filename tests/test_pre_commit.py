from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from bump_deps_index import Options, run

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_mock import MockerFixture


def test_run_pre_commit(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {
        "flake8-bugbear==22.7.1": "flake8-bugbear==22.7.2",
        "black==22.6.0": "black==22.6",
        "prettier@2.7.0": "prettier@2.8",
    }
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
    )
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
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "black==22.6.0 -> black==22.6",
        "flake8-bugbear==22.7.1 -> flake8-bugbear==22.7.2",
        "prettier@2.7.0 -> prettier@2.8",
    }

    setup_cfg = """
    repos:
      - repo: https://github.com/asottile/blacken-docs
        hooks:
          - id: blacken-docs
            additional_dependencies:
            - black==22.6
            - prettier@2.8
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


def test_run_pre_commit_preserves_yaml_layout(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: {"bar": "bar>=2", "baz": "baz>=3", "foo": "foo>=1"}[spec],
    )
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

    successful = run(Options(index_url="I", npm_registry="N", pkgs=[], filenames=[config], pre_release="no"))

    assert successful
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


def test_run_args_empty(capsys: pytest.CaptureFixture[str], mocker: MockerFixture) -> None:
    mocker.patch("bump_deps_index._run.update_spec", side_effect=ValueError)
    run(Options(index_url="https://pypi.org/simple", pkgs=[], filenames=[], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not out

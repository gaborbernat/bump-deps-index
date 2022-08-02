from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from pytest_mock import MockerFixture

from bump_deps_index import Options, run


def test_run_args(capsys: pytest.CaptureFixture[str], mocker: MockerFixture) -> None:
    mapping = {"A": "A>=1", "B": "B"}
    update_spec = mocker.patch(
        "bump_deps_index._run.update_spec", side_effect=lambda _, spec: mapping[spec]  # noqa: U101
    )

    run(Options(index_url="https://pypi.org/simple", pkgs=[" A ", "B", "C"], filename=None))

    out, err = capsys.readouterr()
    assert err == "failed C with KeyError('C')\n"
    assert set(out.splitlines()) == {"A -> A>=1", "B"}

    found = set()
    for called in update_spec.call_args_list:
        assert len(called.args) == 2
        assert called.args[0] == "https://pypi.org/simple"
        found.add(called.args[1])
        assert not called.kwargs
    assert found == {"C", "B", "A"}


def test_run_pyproject_toml(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==2": "B==1", "C": "C>=1"}
    mocker.patch("bump_deps_index._run.update_spec", side_effect=lambda _, spec: mapping[spec])  # noqa: U101
    dest = tmp_path / "pyproject.toml"
    toml = """
    [build-system]
    requires = ["A"]
    [project]
    dependencies = [ "B==2"]
    optional-dependencies.test = [ "C" ]
    optional-dependencies.docs = [ "D"]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", pkgs=[], filename=dest))

    out, err = capsys.readouterr()
    assert err == "failed D with KeyError('D')\n"
    assert set(out.splitlines()) == {"C -> C>=1", "B==2 -> B==1", "A -> A>=1"}

    toml = """
    [build-system]
    requires = ["A>=1"]
    [project]
    dependencies = [ "B==1"]
    optional-dependencies.test = [ "C>=1" ]
    optional-dependencies.docs = [ "D"]
    """
    assert dest.read_text() == dedent(toml).lstrip()


def test_run_tox_ini(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==2": "B==1"}
    mocker.patch("bump_deps_index._run.update_spec", side_effect=lambda _, spec: mapping[spec])  # noqa: U101
    dest = tmp_path / "tox.ini"
    tox_ini = """
    [testenv]
    deps =
        A
    [testenv:ok]
    deps =
        B==2
    [magic]
    deps = NO
    """
    dest.write_text(dedent(tox_ini).lstrip())
    run(Options(index_url="https://pypi.org/simple", pkgs=[], filename=dest))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"B==2 -> B==1", "A -> A>=1"}

    tox_ini = """
    [testenv]
    deps =
        A>=1
    [testenv:ok]
    deps =
        B==1
    [magic]
    deps = NO
    """
    assert dest.read_text() == dedent(tox_ini).lstrip()


def test_run_setup_cfg(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B": "B==1", "C": "C>=3"}
    mocker.patch("bump_deps_index._run.update_spec", side_effect=lambda _, spec: mapping[spec])  # noqa: U101
    dest = tmp_path / "setup.cfg"
    setup_cfg = """
    [options]
    install_requires =
        A
    [options.extras_require]
    testing =
        B
    type =
        C
    """
    dest.write_text(dedent(setup_cfg).lstrip())
    run(Options(index_url="https://pypi.org/simple", pkgs=[], filename=dest))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"B -> B==1", "A -> A>=1", "C -> C>=3"}

    setup_cfg = """
    [options]
    install_requires =
        A>=1
    [options.extras_require]
    testing =
        B==1
    type =
        C>=3
    """
    assert dest.read_text() == dedent(setup_cfg).lstrip()


def test_run_pre_commit(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"flake8-bugbear==22.7.1": "flake8-bugbear==22.7.2", "black==22.6.0": "black==22.6"}
    mocker.patch("bump_deps_index._run.update_spec", side_effect=lambda _, spec: mapping[spec])  # noqa: U101
    dest = tmp_path / ".pre-commit-config.yaml"
    setup_cfg = """
    repos:
      - repo: https://github.com/asottile/blacken-docs
        hooks:
          - id: blacken-docs
            additional_dependencies:
            - black==22.6.0
            - prettier@22
      - repo: https://github.com/PyCQA/flake8
        hooks:
          - id: flake8
            additional_dependencies:
            - flake8-bugbear==22.7.1
    """
    dest.write_text(dedent(setup_cfg).lstrip())
    run(Options(index_url="https://pypi.org/simple", pkgs=[], filename=dest))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"black==22.6.0 -> black==22.6", "flake8-bugbear==22.7.1 -> flake8-bugbear==22.7.2"}

    setup_cfg = """
    repos:
      - repo: https://github.com/asottile/blacken-docs
        hooks:
          - id: blacken-docs
            additional_dependencies:
            - black==22.6
            - prettier@22
      - repo: https://github.com/PyCQA/flake8
        hooks:
          - id: flake8
            additional_dependencies:
            - flake8-bugbear==22.7.2
    """
    assert dest.read_text() == dedent(setup_cfg).lstrip()


def test_run_args_empty(capsys: pytest.CaptureFixture[str], mocker: MockerFixture) -> None:
    mocker.patch("bump_deps_index._run.update_spec", side_effect=ValueError)
    run(Options(index_url="https://pypi.org/simple", pkgs=[], filename=None))

    out, err = capsys.readouterr()
    assert not err
    assert not out

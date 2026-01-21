from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from httpx import Client

from bump_deps_index import Options, main, run
from bump_deps_index._loaders import get_loaders
from bump_deps_index._spec import PkgType

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_run_args(capsys: pytest.CaptureFixture[str], mocker: MockerFixture) -> None:
    mapping = {"A": "A>=1", "B": "B"}
    update_spec = mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )

    run(
        Options(
            index_url="https://pypi.org/simple",
            npm_registry="N",
            pkgs=[" A ", "B", "C"],
            filenames=None,
            pre_release="no",
        ),
    )

    out, err = capsys.readouterr()
    assert err == "failed C with KeyError('C')\n"
    assert set(out.splitlines()) == {"A -> A>=1", "B"}

    found: set[tuple[str, PkgType]] = set()
    for called in update_spec.call_args_list:
        assert len(called.args) == 6
        assert isinstance(called.args[0], Client)
        assert called.args[1] == "https://pypi.org/simple"
        assert called.args[2] == "N"
        found.add((called.args[3], called.args[4]))
        assert called.args[5] is False
        assert not called.kwargs
    assert found == {("C", PkgType.PYTHON), ("B", PkgType.PYTHON), ("A", PkgType.PYTHON)}


def test_run_pyproject_toml(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==2": "B==1", "C": "C>=1", "E": "E>=3", "F": "F>=4"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "pyproject.toml"
    toml = """
    [build-system]
    requires = ["A"]
    [project]
    dependencies = [ "B==2"]
    optional-dependencies.test = [ "C" ]
    optional-dependencies.docs = [ "D"]
    [dependency-groups]
    first = ["E"]
    second = ["F", {include-group = "first"}]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert err == "failed D with KeyError('D')\n"
    assert set(out.splitlines()) == {"C -> C>=1", "F -> F>=4", "A -> A>=1", "E -> E>=3", "B==2 -> B==1"}

    toml = """
    [build-system]
    requires = ["A>=1"]
    [project]
    dependencies = [ "B==1"]
    optional-dependencies.test = [ "C>=1" ]
    optional-dependencies.docs = [ "D"]
    [dependency-groups]
    first = ["E>=3"]
    second = ["F>=4", {include-group = "first"}]
    """
    assert dest.read_text() == dedent(toml).lstrip()


def test_run_pyproject_toml_multiline(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path
) -> None:
    mapping = {"requests>=2.28": "requests>=2.30", "httpx>=0.27": "httpx>=0.28"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "pyproject.toml"
    toml = """
    [project]
    dependencies = [
        "requests>=2.28",
        "httpx>=0.27",
    ]
    [tool.something]
    unrelated = ["should-not-change>=1.0"]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"requests>=2.28 -> requests>=2.30", "httpx>=0.27 -> httpx>=0.28"}

    result = dest.read_text()
    assert "requests>=2.30" in result
    assert "httpx>=0.28" in result
    assert "should-not-change>=1.0" in result


def test_tox_toml(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "tox.toml"
    toml = """
    requires = ["A"]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"A -> A>=1"}

    toml = """
    requires = ["A>=1"]
    """
    assert dest.read_text() == dedent(toml).lstrip()


def test_tox_toml_deps(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B": "B>=2", "C": "C>=3", "D": "D>=4"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "tox.toml"
    toml = """
    requires = ["A"]

    [env_run_base]
    deps = ["B"]

    [env.test]
    deps = ["-r requirements.txt", "C"]

    [env.no_deps]
    description = "no deps here"

    [ui]
    deps = ["D"]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"A -> A>=1", "B -> B>=2", "C -> C>=3", "D -> D>=4"}

    toml = """
    requires = ["A>=1"]

    [env_run_base]
    deps = ["B>=2"]

    [env.test]
    deps = ["-r requirements.txt", "C>=3"]

    [env.no_deps]
    description = "no deps here"

    [ui]
    deps = ["D>=4"]
    """
    assert dest.read_text() == dedent(toml).lstrip()


def test_tox_toml_multiline(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"pytest>=7.0": "pytest>=8.0", "coverage>=6.0": "coverage>=7.0"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "tox.toml"
    toml = """
    [env_run_base]
    deps = [
        "pytest>=7.0",
        "coverage>=6.0",
    ]
    """
    dest.write_text(dedent(toml).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"pytest>=7.0 -> pytest>=8.0", "coverage>=6.0 -> coverage>=7.0"}

    result = dest.read_text()
    assert "pytest>=8.0" in result
    assert "coverage>=7.0" in result


def test_run_pyproject_toml_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "tox.ini"
    dest.write_text("")
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()


def test_run_tox_ini(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==2": "B==1", "C": "C>=3"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "tox.ini"
    tox_ini = """
    [tox]
    requires =
        C
    [testenv]
    deps =
        -e .
        -r requirements.txt
        A
    [testenv:ok]
    deps =
        B==2
    [magic]
    deps = NO
    """
    dest.write_text(dedent(tox_ini).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"A -> A>=1", "B==2 -> B==1", "C -> C>=3"}

    tox_ini = """
    [tox]
    requires =
        C>=3
    [testenv]
    deps =
        -e .
        -r requirements.txt
        A>=1
    [testenv:ok]
    deps =
        B==1
    [magic]
    deps = NO
    """
    assert dest.read_text() == dedent(tox_ini).lstrip()


def test_tox_ini_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "tox.ini"
    dest.write_text("")
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()


def test_run_setup_cfg(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B": "B==1", "C": "C>=3"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
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
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

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


def test_run_setup_cfg_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "setup.cfg"
    dest.write_text("")
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not set(out.splitlines())
    assert not dest.read_text()


def test_run_pre_commit(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {
        "flake8-bugbear==22.7.1": "flake8-bugbear==22.7.2",
        "black==22.6.0": "black==22.6",
        "prettier@2.7.0": "prettier@2.8",
    }
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
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


def test_run_args_empty(capsys: pytest.CaptureFixture[str], mocker: MockerFixture) -> None:
    mocker.patch("bump_deps_index._run.update_spec", side_effect=ValueError)
    run(Options(index_url="https://pypi.org/simple", pkgs=[], filenames=[], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not out


def test_run_requirements_txt(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==1": "B==2"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "requirements.txt"
    req_txt = """
    A
    B==1
    """
    dest.write_text(dedent(req_txt).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"B==1 -> B==2", "A -> A>=1"}

    req_txt = """
    A>=1
    B==2
    """
    assert dest.read_text() == dedent(req_txt).lstrip()


def test_run_requirements_txt_skip_options(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path
) -> None:
    mapping = {"A": "A>=1"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "requirements.txt"
    req_txt = """
    -e .[test]
    -r other.txt
    --index-url https://pypi.org/simple
    A
    """
    dest.write_text(dedent(req_txt).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"A -> A>=1"}

    req_txt = """
    -e .[test]
    -r other.txt
    --index-url https://pypi.org/simple
    A>=1
    """
    assert dest.read_text() == dedent(req_txt).lstrip()


@pytest.mark.parametrize(
    "filename",
    [
        "requirements",
        "requirements.test",
        "requirements-test",
    ],
)
def test_run_requirements_txt_in(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    get_loaders.cache_clear()

    mapping = {"A": "A>=1", "B==1": "B==2"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    (tmp_path / f"{filename}.txt").write_text("C")
    dest = tmp_path / f"{filename}.in"
    req_txt = """
    A
    B==1

    # bad
    """
    dest.write_text(dedent(req_txt).lstrip())
    monkeypatch.chdir(tmp_path)

    main(["--index-url", "https://pypi.org/simple", "--pre-release", "no"])

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"B==1 -> B==2", "A -> A>=1"}

    req_txt = """
    A>=1
    B==2

    # bad
    """
    assert dest.read_text() == dedent(req_txt).lstrip()


def test_run_script_metadata(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    get_loaders.cache_clear()
    mapping = {"rich>=13.9.4": "rich>=13.9.5", "orjson>=3.10.13": "orjson>=3.10.14"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "script.py"
    script = """
    #!/usr/bin/env python3
    # /// script
    # dependencies = [
    #   "rich>=13.9.4",
    #   "orjson>=3.10.13",
    # ]
    # ///

    import rich
    from orjson import dumps

    print("Hello")
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"rich>=13.9.4 -> rich>=13.9.5", "orjson>=3.10.13 -> orjson>=3.10.14"}

    script = """
    #!/usr/bin/env python3
    # /// script
    # dependencies = [
    #   "rich>=13.9.5",
    #   "orjson>=3.10.14",
    # ]
    # ///

    import rich
    from orjson import dumps

    print("Hello")
    """
    assert dest.read_text() == dedent(script).lstrip()


def test_script_metadata_ignores_requires_python(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    get_loaders.cache_clear()
    mapping = {"requests>=2.28": "requests>=2.30"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.11"
    # dependencies = [
    #   "requests>=2.28",
    # ]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"requests>=2.28 -> requests>=2.30"}

    result = dest.read_text()
    assert 'requires-python = ">=3.11"' in result
    assert "requests>=2.30" in result


def test_script_metadata_empty_deps(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    get_loaders.cache_clear()
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = []
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_no_deps_key(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    get_loaders.cache_clear()
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.11"
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_malformed_missing_closing(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    get_loaders.cache_clear()
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [
    #   "requests",
    # ]
    print("Hello")
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_malformed_invalid_toml(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    get_loaders.cache_clear()
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [invalid toml
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_with_extras(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    get_loaders.cache_clear()
    mapping = {"requests[security]>=2.28.0": "requests[security]>=2.30.0"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [
    #   "requests[security]>=2.28.0",
    # ]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"requests[security]>=2.28.0 -> requests[security]>=2.30.0"}


def test_script_metadata_inline_array(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    get_loaders.cache_clear()
    mapping = {"rich>=13.9.4": "rich>=13.9.5", "orjson": "orjson>=3.10.14"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = ["rich>=13.9.4", "orjson"]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"rich>=13.9.4 -> rich>=13.9.5", "orjson -> orjson>=3.10.14"}


def test_script_metadata_file_without_metadata_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    get_loaders.cache_clear()
    dest = tmp_path / "regular.py"
    dest.write_text("import sys\nprint('hello')\n")

    monkeypatch.chdir(tmp_path)

    loaders = get_loaders()
    script_loader = next(loader for loader in loaders if loader.__class__.__name__ == "ScriptMetadata")

    assert dest not in list(script_loader.files)


def test_script_metadata_malformed_invalid_comment_prefix(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    get_loaders.cache_clear()
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [
    invalid line without comment prefix
    # ]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_file_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    get_loaders.cache_clear()
    script_file = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = ["requests"]
    # ///
    """
    script_file.write_text(dedent(script).lstrip())

    broken_link = tmp_path / "broken.py"
    broken_link.symlink_to(tmp_path / "nonexistent.py")

    monkeypatch.chdir(tmp_path)

    loaders = get_loaders()
    script_loader = next(loader for loader in loaders if loader.__class__.__name__ == "ScriptMetadata")

    found_files = list(script_loader.files)
    assert script_file in found_files
    assert broken_link not in found_files


def test_script_metadata_supports_file_read_error(tmp_path: Path) -> None:
    get_loaders.cache_clear()
    broken_link = tmp_path / "broken.py"
    broken_link.symlink_to(tmp_path / "nonexistent.py")

    loaders = get_loaders()
    script_loader = next(loader for loader in loaders if loader.__class__.__name__ == "ScriptMetadata")

    assert not script_loader.supports(broken_link)


def test_script_metadata_with_blank_line_in_toml(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    get_loaders.cache_clear()
    mapping = {"requests>=2.28": "requests>=2.30"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.11"
    #
    # dependencies = [
    #   "requests>=2.28",
    # ]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"requests>=2.28 -> requests>=2.30"}


def test_script_metadata_file_unicode_decode_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    get_loaders.cache_clear()
    script_file = tmp_path / "valid.py"
    script = """
    # /// script
    # dependencies = ["requests"]
    # ///
    """
    script_file.write_text(dedent(script).lstrip())

    invalid_file = tmp_path / "invalid.py"
    invalid_file.write_bytes(b"# /// script\n\xff\xfe")

    monkeypatch.chdir(tmp_path)

    loaders = get_loaders()
    script_loader = next(loader for loader in loaders if loader.__class__.__name__ == "ScriptMetadata")

    found_files = list(script_loader.files)
    assert script_file in found_files
    assert invalid_file not in found_files


def test_script_metadata_only_replaces_in_block(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    get_loaders.cache_clear()
    mapping = {"httpx>=0.27.0": "httpx>=0.28.1", "rich>=13.0.0": "rich>=14.2"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, __, ___, spec, ____, _____: mapping[spec],
    )
    dest = tmp_path / "script.py"
    script = """
    #!/usr/bin/env python3
    # /// script
    # requires-python = ">=3.11"
    # dependencies = [
    #     "httpx>=0.27.0",
    #     "rich>=13.0.0",
    # ]
    # ///
    from __future__ import annotations

    import httpx
    from rich import print

    # This should NOT be changed: httpx>=0.27.0
    x = "httpx>=0.27.0"
    y = "rich>=13.0.0"

    print("Hello")
    """
    dest.write_text(dedent(script).lstrip())
    run(Options(index_url="https://pypi.org/simple", npm_registry="", pkgs=[], filenames=[dest], pre_release="no"))

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {"httpx>=0.27.0 -> httpx>=0.28.1", "rich>=13.0.0 -> rich>=14.2"}

    result = dest.read_text()
    assert "httpx>=0.28.1" in result
    assert "rich>=14.2" in result
    assert "# This should NOT be changed: httpx>=0.27.0" in result
    assert 'x = "httpx>=0.27.0"' in result
    assert 'y = "rich>=13.0.0"' in result

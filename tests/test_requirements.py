from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from bump_deps_index import Options, main, run
from bump_deps_index._loaders import get_loaders

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_run_requirements_txt(capsys: pytest.CaptureFixture[str], mocker: MockerFixture, tmp_path: Path) -> None:
    mapping = {"A": "A>=1", "B==1": "B==2"}
    mocker.patch(
        "bump_deps_index._run.update_spec",
        side_effect=lambda _, spec, __, ___: mapping[spec],
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
        side_effect=lambda _, spec, __, ___: mapping[spec],
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


def test_run_requirements_txt_preserves_hashes(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("bump_deps_index._run.update_spec", side_effect=lambda _, spec, __, ___: f"{spec}>=2")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("A \\\n    --hash=sha256:123\n", encoding="utf-8")

    successful = run(Options(index_url="I", npm_registry="N", pkgs=[], filenames=[requirements], pre_release="no"))

    assert successful
    assert requirements.read_text(encoding="utf-8") == "A>=2 \\\n    --hash=sha256:123\n"


def test_run_requirements_txt_distinguishes_markers_from_comments(mocker: MockerFixture, tmp_path: Path) -> None:
    old = 'A; os_name == "foo # bar"'
    new = 'A>=2; os_name == "foo # bar"'
    mocker.patch("bump_deps_index._run.update_spec", return_value=new)
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(f"{old}  # keep this reason\n", encoding="utf-8")

    successful = run(Options(index_url="I", npm_registry="N", pkgs=[], filenames=[requirements], pre_release="no"))

    assert successful
    assert requirements.read_text(encoding="utf-8") == f"{new}  # keep this reason\n"


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
        side_effect=lambda _, spec, __, ___: mapping[spec],
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

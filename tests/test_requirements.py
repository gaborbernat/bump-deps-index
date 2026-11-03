from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeIndex
    from pytest_httpx import HTTPXMock


@dataclass(frozen=True, slots=True, kw_only=True)
class _Case:
    content: str
    pypi: dict[str, list[str]]
    updates: set[str]
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _Case(
                content="A\nB==1\n",
                pypi={"A": ["1"], "B": ["1", "2"]},
                updates={"B==1 -> B==2", "A -> A>=1"},
                expected="A>=1\nB==2\n",
            ),
            id="pinned-and-unpinned",
        ),
        pytest.param(
            _Case(
                content="-e .[test]\n-r other.txt\n--index-url https://pypi.org/simple\nA\n",
                pypi={"A": ["1"]},
                updates={"A -> A>=1"},
                expected="-e .[test]\n-r other.txt\n--index-url https://pypi.org/simple\nA>=1\n",
            ),
            id="skips-options",
        ),
    ],
)
def test_run_requirements_txt_updates_dependencies(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path, case: _Case
) -> None:
    index.pypi.update(case.pypi)
    dest = tmp_path / "requirements.txt"
    dest.write_text(case.content)

    assert index.run(dest)

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == ("", {"Using Python index: https://pypi.example/simple", *case.updates})
    assert dest.read_text() == case.expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(
            "A \\\n    --hash=sha256:123\nB --hash=sha256:456\nD\n",
            "A \\\n    --hash=sha256:123\nB --hash=sha256:456\nD>=2\n",
            id="hashed",
        ),
        pytest.param(
            "./local\nhttps://example.com/a.whl\n${PKG}\nD\n",
            "./local\nhttps://example.com/a.whl\n${PKG}\nD>=2\n",
            id="without-name",
        ),
    ],
)
def test_run_requirements_txt_skips_entries(index: FakeIndex, tmp_path: Path, content: str, expected: str) -> None:
    index.pypi["D"] = ["2"]
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(content, encoding="utf-8")

    assert index.run(requirements)

    assert requirements.read_text(encoding="utf-8") == expected


def test_run_requirements_txt_distinguishes_markers_from_comments(index: FakeIndex, tmp_path: Path) -> None:
    index.pypi["A"] = ["2"]
    requirements = tmp_path / "requirements.txt"
    requirements.write_text('A>=1; os_name == "foo # bar"  # keep this reason\n', encoding="utf-8")

    assert index.run(requirements)

    assert requirements.read_text(encoding="utf-8") == 'A>=2; os_name == "foo # bar"  # keep this reason\n'


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("requirements", id="plain-name"),
        pytest.param("requirements.test", id="dotted-suffix"),
        pytest.param("requirements-test", id="dashed-suffix"),
    ],
)
def test_run_requirements_txt_in(
    capsys: pytest.CaptureFixture[str],
    index: FakeIndex,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    index.pypi.update(A=["1"], B=["1", "2"])
    (tmp_path / f"{filename}.txt").write_text("C")
    dest = tmp_path / f"{filename}.in"
    content = """
    A
    B==1

    # bad
    """
    dest.write_text(dedent(content).lstrip())
    monkeypatch.chdir(tmp_path)

    main(["--index-url", index.index_url, "--pre-release", "no"])

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == (
        "",
        {"Using Python index: https://pypi.example/simple", "B==1 -> B==2", "A -> A>=1"},
    )

    expected = """
    A>=1
    B==2

    # bad
    """
    assert dest.read_text() == dedent(expected).lstrip()


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(
            "C \\\n  ; python_version > '3'\n",
            "C>=2 \\\n  ; python_version > '3'\n",
            id="edit-first-line",
        ),
        pytest.param(
            "C \\\n  >=1 ; python_version > '3'  # why\n",
            "C \\\n  >=2 ; python_version > '3'  # why\n",
            id="edit-continuation-line",
        ),
    ],
)
def test_run_requirements_txt_updates_continued_entries(
    index: FakeIndex, tmp_path: Path, content: str, expected: str
) -> None:
    index.pypi["C"] = ["2"]
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(content, encoding="utf-8")

    assert index.run(requirements)

    assert requirements.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("--index-url\thttps://ignored.example/simple\n-r base.txt\nfoo>=1\n", id="included-file"),
        pytest.param("-i \\\n  'https://${HOST}/simple'\nfoo>=1\n", id="continued-and-quoted"),
        pytest.param("-i 'unclosed\n--index-url=https://${HOST}/simple # mirror\nfoo>=1\n", id="equals-and-comment"),
        pytest.param(
            "-i https://private.\\\nexample/simple\n# try -i https://ignored.example/simple \\\n"
            "  # -r other.txt\nfoo>=1\n",
            id="joined-without-space-and-comment-lines",
        ),
    ],
)
def test_run_requirements_txt_looks_up_its_own_index(
    httpx_mock: HTTPXMock, index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: str
) -> None:
    monkeypatch.setenv("HOST", "private.example")
    index.pypi["foo"] = ["2"]
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(content, encoding="utf-8")
    base = "-ihttps://${HOST}/simple  # mirror\n-r requirements.txt\n-r missing.txt\n"
    (tmp_path / "base.txt").write_text(base, encoding="utf-8")

    assert index.run(requirements)

    assert (requirements.read_text(encoding="utf-8"), [str(request.url) for request in httpx_mock.get_requests()]) == (
        content.replace("foo>=1", "foo>=2"),
        ["https://private.example/simple/foo/"],
    )


def test_run_requirements_txt_keeps_unset_and_empty_variables(
    httpx_mock: HTTPXMock, index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("UNSET", raising=False)
    monkeypatch.setenv("EMPTY", "")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "-i https://a.example/${UNSET}\n--extra-index-url=https://b.example/${EMPTY}\nfoo\n", encoding="utf-8"
    )

    index.run(requirements)

    assert sorted(str(request.url) for request in httpx_mock.get_requests()) == [
        "https://a.example/$%7BUNSET%7D/foo/",
        "https://b.example/$%7BEMPTY%7D/foo/",
    ]

from __future__ import annotations

import os
from dataclasses import replace
from threading import Event
from typing import TYPE_CHECKING

import pytest
from conftest import PYPI_FOO, index_args

from bump_deps_index import main
from bump_deps_index._ecosystems._table import ECOSYSTEMS
from bump_deps_index._lookup import PkgType

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock

    from bump_deps_index._ecosystems._common._candidates import Candidates


def test_run_args(capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/b/", text="")
    httpx_mock.add_response(url="https://pypi.example/simple/c/", status_code=404)
    httpx_mock.add_response(url="https://npm.example/@scope%2Fpkg", json={"versions": {"1.0.0": {}, "2.0.0": {}}})
    httpx_mock.add_response(url="https://npm.example/pkg", json={"versions": {"2.0.0": {}}})

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args(" A ", "B", "C", "@scope/pkg@1", "direct @ https://example.com/direct.whl", "pkg@1"))

    out, err = capsys.readouterr()
    assert err.startswith(
        "failed to look up C, so it was not updated: HTTPStatusError(\"Client error '404 Not Found' for url "
    )
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "Using JavaScript index: https://npm.example",
        "A -> A>=1",
        "B",
        "@scope/pkg@1 -> @scope/pkg@2.0.0",
        "direct @ https://example.com/direct.whl",
        "pkg@1 -> pkg@2.0.0",
    }


def test_run_args_without_pyproject_keeps_index_selection(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="https://pypi.example/simple/a/", text='<a data-requires-python="&gt;=4">a-2.tar.gz</a>'
    )

    main(index_args("A"))

    assert capsys.readouterr().out.splitlines() == ["Using Python index: https://pypi.example/simple", "A -> A>=2"]


def test_run_args_empty(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f"))

    assert capsys.readouterr() == (
        "",
        "no supported dependency files found in the working directory; pass --file or packages\n",
    )


@pytest.mark.parametrize(
    ("name", "message"),
    [
        pytest.param("dependencies.json", "{} is not a supported dependency file, so it was skipped", id="unsupported"),
        pytest.param("tox.toml", "{} does not exist; pass a file that exists to --file", id="missing"),
    ],
)
def test_run_rejects_file(capsys: pytest.CaptureFixture[str], tmp_path: Path, name: str, message: str) -> None:
    (tmp_path / "dependencies.json").touch()
    filename = tmp_path / name

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(filename)))

    assert capsys.readouterr().err == f"{message.format(filename)}\n"


def test_run_reports_unparsable_pyproject_and_continues(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-1.tar.gz</a>")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project\n")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("A\n")
    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(pyproject), str(requirements)))

    error = "TOMLDecodeError(\"Expected ']' at the end of a table declaration (at line 1, column 9)\")"
    assert capsys.readouterr().err.splitlines() == [
        f"failed to read {pyproject}, so it was skipped: {error}",
        f"ignoring project metadata from {pyproject}, so its uv settings are not read: {error}",
    ]
    assert (pyproject.read_text(), requirements.read_text()) == ("[project\n", "A>=1\n")


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("pyproject.toml", id="pyproject"),
        pytest.param("tox.toml", id="tox-toml"),
        pytest.param("tox.ini", id="tox-ini"),
        pytest.param("setup.cfg", id="setup-cfg"),
        pytest.param(".pre-commit-config.yaml", id="pre-commit"),
        pytest.param("requirements.txt", id="requirements"),
    ],
)
def test_empty_file_stays_empty(capsys: pytest.CaptureFixture[str], tmp_path: Path, name: str) -> None:
    dest = tmp_path / name
    dest.write_text("")

    main(index_args("-f", str(dest)))

    assert (*capsys.readouterr(), dest.read_text()) == ("", "", "")


def test_unchanged_file_is_not_rewritten(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/foo/", text="<a>foo-2.tar.gz</a>")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo>=2\n", encoding="utf-8")
    os.utime(requirements, ns=(0, 0))

    main(index_args("-f", str(requirements)))

    assert requirements.stat().st_mtime_ns == 0


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "requirements.txt",
            b"foo>=1\r\nbar>=1\r\nbar>=1\n",
            b"foo>=2\r\nbar>=1\r\nbar>=1\n",
            {**PYPI_FOO, "https://pypi.example/simple/bar/": "<a>bar-1.tar.gz</a>"},
            id="mixed",
        ),
        pytest.param(
            "tox.ini", b"[testenv]\rdeps = foo>=1\r", b"[testenv]\rdeps = foo>=2\r", PYPI_FOO, id="carriage-return"
        ),
        pytest.param(
            "pyproject.toml",
            b'[project]\nname = "demo"\ndependencies = ["""foo\\\n>=1"""]\n# a\r\n# b\r\n# c\n',
            b'[project]\nname = "demo"\ndependencies = ["""foo>=2"""]\n# a\r\n# b\r\n# c\n',
            PYPI_FOO,
            id="joined-line",
        ),
    ],
    indirect=["pages"],
)
@pytest.mark.usefixtures("pages")
def test_file_keeps_each_line_ending(tmp_path: Path, name: str, content: bytes, expected: bytes) -> None:
    dest = tmp_path / name
    dest.write_bytes(content)

    main(index_args("-f", str(dest)))

    assert dest.read_bytes() == expected


def test_package_shared_across_files_is_fetched_once(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/foo/", text="<a>foo-2.tar.gz</a>")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo>=1\n", encoding="utf-8")
    tox_toml = tmp_path / "tox.toml"
    tox_toml.write_text('[env_run_base]\ndeps = ["foo>=1", "foo>=1.5"]\n', encoding="utf-8")

    main(index_args("-f", str(requirements), str(tox_toml)))

    assert (requirements.read_text(encoding="utf-8"), tox_toml.read_text(encoding="utf-8")) == (
        "foo>=2\n",
        '[env_run_base]\ndeps = ["foo>=2", "foo>=2"]\n',
    )
    assert len(httpx_mock.get_requests()) == 1


def test_output_follows_file_order(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/a/", text="<a>a-2.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/b/", text="<a>b-2.tar.gz</a>")
    b_updated = Event()
    python = ECOSYSTEMS[PkgType.PYTHON]

    def bump_b_first(spec: str, candidates: Candidates) -> str:
        if spec == "a":
            b_updated.wait(timeout=5)  # `a` finishes after `b`, so only the reporting keeps the file order
        result = python.bump(spec, candidates)
        if spec == "b":
            b_updated.set()
        return result

    monkeypatch.setitem(ECOSYSTEMS, PkgType.PYTHON, replace(python, bump=bump_b_first))
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("a\nb\n", encoding="utf-8")

    main(index_args("-f", str(requirements)))

    assert capsys.readouterr().out.splitlines() == [
        "Using Python index: https://pypi.example/simple",
        "a -> a>=2",
        "b -> b>=2",
    ]


def test_requires_python_comes_from_nearest_pyproject(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.9"\n')
    (tmp_path / "requirements").mkdir()
    requirements = tmp_path / "requirements" / "requirements-dev.txt"
    requirements.write_text("foo\n", encoding="utf-8")
    httpx_mock.add_response(
        url="https://pypi.example/simple/foo/",
        text='<a>foo-1.tar.gz</a><a data-requires-python="&gt;=3.10">foo-2.tar.gz</a>',
    )

    main(index_args("-f", str(requirements)))

    assert requirements.read_text(encoding="utf-8") == "foo>=1\n"


@pytest.mark.parametrize(
    "pyproject",
    [
        pytest.param('project = "x"', id="project-not-a-table"),
        pytest.param("[project]\nname = 1", id="name-not-a-string"),
        pytest.param('[project]\nname = "demo"\nrequires-python = 3', id="requires-python-not-a-string"),
    ],
)
def test_requirements_next_to_mistyped_pyproject(httpx_mock: HTTPXMock, tmp_path: Path, pyproject: str) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/foo/", text="<a>foo-2.tar.gz</a>")
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo>=1\n", encoding="utf-8")

    main(index_args("-f", str(requirements)))

    assert requirements.read_text(encoding="utf-8") == "foo>=2\n"


@pytest.mark.usefixtures("isolated_index_settings")
def test_run_prints_index_once_without_credentials(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(url="https://user:secret@pypi.example:8443/simple/a/", text="<a>a-1.tar.gz</a>")
    httpx_mock.add_response(url="https://user:secret@pypi.example:8443/simple/b/", text="<a>b-2.tar.gz</a>")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("a\nb\n")

    main([
        "-i",
        "https://user:secret@pypi.example:8443/simple",
        "-p",
        "no",
        "--no-exclude-newer",
        "-f",
        str(requirements),
    ])

    lines = capsys.readouterr().out.splitlines()
    assert (lines[0], sorted(lines[1:])) == (
        "Using Python index: https://pypi.example:8443/simple",
        ["a -> a>=1", "b -> b>=2"],
    )


def test_failure_message_redacts_index_credentials(
    tmp_path: Path, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo\n", encoding="utf-8")
    index_url = "https://user:s3c'ret@pypi.example/simple"
    httpx_mock.add_response(url=f"{index_url}/foo/", status_code=404)

    with pytest.raises(SystemExit, match=r"^1$"):
        main(["-i", index_url, "-p", "no", "--no-exclude-newer", "-f", str(requirements)])

    assert capsys.readouterr().err.startswith(
        "failed to look up foo, so it was not updated: HTTPStatusError(\"Client error '404 Not Found' for url 'https://pypi.example/simple/foo/'"
    )


def test_output_redacts_direct_reference_credentials(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    requirements = tmp_path / "requirements.txt"
    content = "foo @ https://user:s3cret@files.example/foo-1.0-py3-none-any.whl\n"
    requirements.write_text(content, encoding="utf-8")

    main(index_args("-f", str(requirements)))

    assert (capsys.readouterr().out.splitlines(), requirements.read_text(encoding="utf-8")) == (
        ["Using Python index: https://pypi.example/simple", "foo @ https://files.example/foo-1.0-py3-none-any.whl"],
        content,
    )

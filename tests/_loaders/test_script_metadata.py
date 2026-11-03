from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from conftest import PYPI_FOO, Case, index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            Case(
                content="""
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
            """,
                pages={
                    "https://pypi.example/simple/rich/": "<a>rich-13.9.5.tar.gz</a>",
                    "https://pypi.example/simple/orjson/": "<a>orjson-3.10.14.tar.gz</a>",
                },
                updates={"rich>=13.9.4 -> rich>=13.9.5", "orjson>=3.10.13 -> orjson>=3.10.14"},
                expected="""
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
            """,
            ),
            id="multiline-array",
        ),
        pytest.param(
            Case(
                content="""
            # /// script
            # requires-python = ">=3.11"
            # dependencies = [
            #   "requests>=2.28",
            # ]
            # ///
            """,
                pages={"https://pypi.example/simple/requests/": "<a>requests-2.30.tar.gz</a>"},
                updates={"requests>=2.28 -> requests>=2.30"},
                expected="""
            # /// script
            # requires-python = ">=3.11"
            # dependencies = [
            #   "requests>=2.30",
            # ]
            # ///
            """,
            ),
            id="keeps-requires-python-line",
        ),
        pytest.param(
            Case(
                content="""
            # /// script
            # dependencies = [
            #   "requests[security]>=2.28.0",
            # ]
            # ///
            """,
                pages={"https://pypi.example/simple/requests/": "<a>requests-2.30.1.tar.gz</a>"},
                updates={"requests[security]>=2.28.0 -> requests[security]>=2.30.1"},
                expected="""
            # /// script
            # dependencies = [
            #   "requests[security]>=2.30.1",
            # ]
            # ///
            """,
            ),
            id="with-extras",
        ),
        pytest.param(
            Case(
                content="""
            # /// script
            # dependencies = ["rich>=13.9.4", "orjson"]
            # ///
            """,
                pages={
                    "https://pypi.example/simple/rich/": "<a>rich-13.9.5.tar.gz</a>",
                    "https://pypi.example/simple/orjson/": "<a>orjson-3.10.14.tar.gz</a>",
                },
                updates={"rich>=13.9.4 -> rich>=13.9.5", "orjson -> orjson>=3.10.14"},
                expected="""
            # /// script
            # dependencies = ["rich>=13.9.5", "orjson>=3.10.14"]
            # ///
            """,
            ),
            id="inline-array",
        ),
        pytest.param(
            Case(
                content="""
            # /// script
            # requires-python = ">=3.11"
            #
            # dependencies = [
            #   "requests>=2.28",
            # ]
            # ///
            """,
                pages={"https://pypi.example/simple/requests/": "<a>requests-2.30.tar.gz</a>"},
                updates={"requests>=2.28 -> requests>=2.30"},
                expected="""
            # /// script
            # requires-python = ">=3.11"
            #
            # dependencies = [
            #   "requests>=2.30",
            # ]
            # ///
            """,
            ),
            id="blank-line-in-toml",
        ),
    ],
)
def test_script_metadata_updates_dependencies(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, tmp_path: Path, case: Case
) -> None:
    for url, page in case.pages.items():
        httpx_mock.add_response(url=url, text=page)
    dest = tmp_path / "script.py"
    dest.write_text(dedent(case.content).lstrip())

    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == ("", {"Using Python index: https://pypi.example/simple", *case.updates})
    assert dest.read_text() == dedent(case.expected).lstrip()


@pytest.mark.parametrize(
    "script",
    [
        pytest.param("# /// script\n# dependencies = []\n# ///\n", id="empty-dependencies"),
        pytest.param('# /// script\n# requires-python = ">=3.11"\n# ///\n', id="no-dependencies-key"),
        pytest.param('# /// script\n# dependencies = [\n#   "requests",\n# ]\nprint("Hello")\n', id="missing-closing"),
        pytest.param("# /// script\n# dependencies = [invalid toml\n# ///\n", id="invalid-toml"),
        pytest.param(
            "# /// script\n# dependencies = [\ninvalid line without comment prefix\n# ]\n# ///\n",
            id="line-without-comment-prefix",
        ),
    ],
)
def test_script_metadata_without_dependencies_does_nothing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, script: str
) -> None:
    dest = tmp_path / "script.py"
    dest.write_text(script)

    main(index_args("-f", str(dest)))

    assert (capsys.readouterr(), dest.read_text()) == (("", ""), script)


def test_script_metadata_only_replaces_in_block(
    capsys: pytest.CaptureFixture[str],
    httpx_mock: HTTPXMock,
    tmp_path: Path,
) -> None:
    httpx_mock.add_response(url="https://pypi.example/simple/httpx/", text="<a>httpx-0.28.1.tar.gz</a>")
    httpx_mock.add_response(url="https://pypi.example/simple/rich/", text="<a>rich-14.2.tar.gz</a>")
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
    main(index_args("-f", str(dest)))

    out, err = capsys.readouterr()
    assert (err, set(out.splitlines())) == (
        "",
        {
            "Using Python index: https://pypi.example/simple",
            "httpx>=0.27.0 -> httpx>=0.28.1",
            "rich>=13.0.0 -> rich>=14.2",
        },
    )

    expected = """
    #!/usr/bin/env python3
    # /// script
    # requires-python = ">=3.11"
    # dependencies = [
    #     "httpx>=0.28.1",
    #     "rich>=14.2",
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
    assert dest.read_text() == dedent(expected).lstrip()


def test_script_metadata_uses_own_requires_python(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.12"\n')
    httpx_mock.add_response(
        url="https://pypi.example/simple/foo/",
        text='<a>foo-1.tar.gz</a><a data-requires-python="&gt;=3.10">foo-2.tar.gz</a>',
    )
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.9"
    # dependencies = ["foo"]
    # ///
    """
    dest.write_text(dedent(script).lstrip())

    main(index_args("-f", str(dest)))

    assert dest.read_text() == dedent(script).lstrip().replace('["foo"]', '["foo>=1"]')


def test_script_metadata_reports_invalid_requires_python(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.9.*"
    # dependencies = ["foo"]
    # ///
    """
    dest.write_text(dedent(script).lstrip())

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(dest)))

    assert (
        capsys.readouterr().err
        == f"failed to read {dest}, so it was skipped: InvalidSpecifier(\"Invalid specifier: '>=3.9.*'\")\n"
    )


def test_script_metadata_discovery_skips_unreadable_and_plain_files(
    capsys: pytest.CaptureFixture[str], httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(url="https://pypi.example/simple/requests/", text="<a>requests-2.tar.gz</a>")
    script = tmp_path / "valid.py"
    script.write_text('# /// script\n# dependencies = ["requests"]\n# ///\n')
    (tmp_path / "regular.py").write_text("import sys\n")
    (tmp_path / "broken.py").symlink_to(tmp_path / "nonexistent.py")
    (tmp_path / "invalid.py").write_bytes(b"# /// script\n\xff\xfe")

    main(["-i", "https://pypi.example/simple"])

    assert (capsys.readouterr(), script.read_text()) == (
        ("Using Python index: https://pypi.example/simple\nrequests -> requests>=2\n", ""),
        '# /// script\n# dependencies = ["requests>=2"]\n# ///\n',
    )


def test_script_metadata_rejects_undecodable_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.py"
    invalid.write_bytes(b"# /// script\n\xff\xfe")

    with pytest.raises(SystemExit, match=r"^1$"):
        main(index_args("-f", str(invalid)))

    assert capsys.readouterr().err == f"{invalid} is not a supported dependency file, so it was skipped\n"


@pytest.mark.parametrize(
    ("name", "content", "expected", "pages"),
    [
        pytest.param(
            "script.py",
            """
            # /// script
            # dependencies = ["foo>=1"]
            # [tool.uv]
            # constraint-dependencies = ["foo>=1"]
            # ///
            """,
            """
            # /// script
            # dependencies = ["foo>=2"]
            # [tool.uv]
            # constraint-dependencies = ["foo>=1"]
            # ///
            """,
            PYPI_FOO,
            id="script-only-dependencies",
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

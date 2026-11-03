from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeIndex


@dataclass(frozen=True, slots=True, kw_only=True)
class _Case:
    script: str
    pypi: dict[str, list[str]]
    updates: set[str]
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _Case(
                script="""
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
                pypi={"rich": ["13.9.5"], "orjson": ["3.10.14"]},
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
            _Case(
                script="""
            # /// script
            # requires-python = ">=3.11"
            # dependencies = [
            #   "requests>=2.28",
            # ]
            # ///
            """,
                pypi={"requests": ["2.30"]},
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
            _Case(
                script="""
            # /// script
            # dependencies = [
            #   "requests[security]>=2.28.0",
            # ]
            # ///
            """,
                pypi={"requests": ["2.30.1"]},
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
            _Case(
                script="""
            # /// script
            # dependencies = ["rich>=13.9.4", "orjson"]
            # ///
            """,
                pypi={"rich": ["13.9.5"], "orjson": ["3.10.14"]},
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
            _Case(
                script="""
            # /// script
            # requires-python = ">=3.11"
            #
            # dependencies = [
            #   "requests>=2.28",
            # ]
            # ///
            """,
                pypi={"requests": ["2.30"]},
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
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path, case: _Case
) -> None:
    index.pypi.update(case.pypi)
    dest = tmp_path / "script.py"
    dest.write_text(dedent(case.script).lstrip())

    assert index.run(dest)

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
    capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex, script: str
) -> None:
    dest = tmp_path / "script.py"
    dest.write_text(script)

    assert index.run(dest)

    assert (capsys.readouterr(), dest.read_text()) == (("", ""), script)


def test_script_metadata_only_replaces_in_block(
    capsys: pytest.CaptureFixture[str],
    index: FakeIndex,
    tmp_path: Path,
) -> None:
    index.pypi.update({"httpx": ["0.28.1"], "rich": ["14.2"]})
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
    assert index.run(dest)

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


def test_script_metadata_uses_own_requires_python(index: FakeIndex, tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.12"\n')
    index.pypi["foo"] = ["1", "2"]
    index.requires_python["foo-2.tar.gz"] = ">=3.10"
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.9"
    # dependencies = ["foo"]
    # ///
    """
    dest.write_text(dedent(script).lstrip())

    assert index.run(dest)

    assert dest.read_text() == dedent(script).lstrip().replace('["foo"]', '["foo>=1"]')


def test_script_metadata_reports_invalid_requires_python(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path
) -> None:
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.9.*"
    # dependencies = ["foo"]
    # ///
    """
    dest.write_text(dedent(script).lstrip())

    assert not index.run(dest)

    assert (
        capsys.readouterr().err
        == f"failed to read {dest}, so it was skipped: InvalidSpecifier(\"Invalid specifier: '>=3.9.*'\")\n"
    )


def test_script_metadata_discovery_skips_unreadable_and_plain_files(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    index.pypi["requests"] = ["2"]
    script = tmp_path / "valid.py"
    script.write_text('# /// script\n# dependencies = ["requests"]\n# ///\n')
    (tmp_path / "regular.py").write_text("import sys\n")
    (tmp_path / "broken.py").symlink_to(tmp_path / "nonexistent.py")
    (tmp_path / "invalid.py").write_bytes(b"# /// script\n\xff\xfe")

    main(["-i", index.index_url])

    assert (capsys.readouterr(), script.read_text()) == (
        ("Using Python index: https://pypi.example/simple\nrequests -> requests>=2\n", ""),
        '# /// script\n# dependencies = ["requests>=2"]\n# ///\n',
    )


def test_script_metadata_rejects_undecodable_file(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path
) -> None:
    invalid = tmp_path / "invalid.py"
    invalid.write_bytes(b"# /// script\n\xff\xfe")

    assert not index.run(invalid)

    assert capsys.readouterr().err == f"{invalid} is not a supported dependency file, so it was skipped\n"

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from conftest import FakeIndex


def test_run_script_metadata(capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path) -> None:
    index.pypi.update({"rich": ["13.9.5"], "orjson": ["3.10.14"]})
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
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "rich>=13.9.4 -> rich>=13.9.5",
        "orjson>=3.10.13 -> orjson>=3.10.14",
    }

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


def test_script_metadata_keeps_requires_python_line(
    capsys: pytest.CaptureFixture[str],
    index: FakeIndex,
    tmp_path: Path,
) -> None:
    index.pypi.update({"requests": ["2.30"]})
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
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "requests>=2.28 -> requests>=2.30",
    }

    assert dest.read_text() == dedent(script).lstrip().replace("2.28", "2.30")


def test_script_metadata_empty_deps(capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex) -> None:
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = []
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_no_deps_key(capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex) -> None:
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # requires-python = ">=3.11"
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_malformed_missing_closing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex
) -> None:
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [
    #   "requests",
    # ]
    print("Hello")
    """
    dest.write_text(dedent(script).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_malformed_invalid_toml(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex
) -> None:
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [invalid toml
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_with_extras(
    capsys: pytest.CaptureFixture[str],
    index: FakeIndex,
    tmp_path: Path,
) -> None:
    index.pypi.update({"requests": ["2.30.1"]})
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [
    #   "requests[security]>=2.28.0",
    # ]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "requests[security]>=2.28.0 -> requests[security]>=2.30.1",
    }


def test_script_metadata_inline_array(
    capsys: pytest.CaptureFixture[str],
    index: FakeIndex,
    tmp_path: Path,
) -> None:
    index.pypi.update({"rich": ["13.9.5"], "orjson": ["3.10.14"]})
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = ["rich>=13.9.4", "orjson"]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "rich>=13.9.4 -> rich>=13.9.5",
        "orjson -> orjson>=3.10.14",
    }


def test_script_metadata_malformed_invalid_comment_prefix(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, index: FakeIndex
) -> None:
    dest = tmp_path / "script.py"
    script = """
    # /// script
    # dependencies = [
    invalid line without comment prefix
    # ]
    # ///
    """
    dest.write_text(dedent(script).lstrip())
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert not out.strip()


def test_script_metadata_with_blank_line_in_toml(
    capsys: pytest.CaptureFixture[str],
    index: FakeIndex,
    tmp_path: Path,
) -> None:
    index.pypi.update({"requests": ["2.30"]})
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
    assert index.run(dest)

    out, err = capsys.readouterr()
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "requests>=2.28 -> requests>=2.30",
    }


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
    assert not err
    assert set(out.splitlines()) == {
        "Using Python index: https://pypi.example/simple",
        "httpx>=0.27.0 -> httpx>=0.28.1",
        "rich>=13.0.0 -> rich>=14.2",
    }

    updated = dedent(script).lstrip().replace('#     "httpx>=0.27.0"', '#     "httpx>=0.28.1"')
    assert dest.read_text() == updated.replace('#     "rich>=13.0.0"', '#     "rich>=14.2"')


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

    assert capsys.readouterr().err == f"failed to read {dest} with InvalidSpecifier(\"Invalid specifier: '>=3.9.*'\")\n"


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

    assert capsys.readouterr().err == f"we do not support {invalid}\n"

from __future__ import annotations

from configparser import RawConfigParser
from typing import TYPE_CHECKING

from conftest import index_args

from bump_deps_index import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_httpx import HTTPXMock


def test_ini_files_read_as_utf8(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # stand in for a locale that cannot decode UTF-8, such as the `C` locale or cp1252 on Windows
    read = RawConfigParser.read
    monkeypatch.setattr(
        RawConfigParser,
        "read",
        lambda self, filenames, encoding=None: read(self, filenames, encoding=encoding or "ascii"),
    )
    httpx_mock.add_response(url="https://pypi.example/simple/foo/", text="<a>foo-2.tar.gz</a>")
    (tox_ini := tmp_path / "tox.ini").write_text("[testenv]\ndescription = tëst\ndeps = foo>=1\n", encoding="utf-8")
    (setup_cfg := tmp_path / "setup.cfg").write_text(
        "[metadata]\nname = ë\n[options]\ninstall_requires = foo>=1\n", encoding="utf-8"
    )

    main(index_args("-f", str(tox_ini), str(setup_cfg)))

    assert [file.read_text(encoding="utf-8").splitlines()[-1] for file in (tox_ini, setup_cfg)] == [
        "deps = foo>=2",
        "install_requires = foo>=2",
    ]

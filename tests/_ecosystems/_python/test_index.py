from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

import httpx
import pytest

if TYPE_CHECKING:
    from conftest import Bump

pytestmark: Final[pytest.MarkDecorator] = pytest.mark.usefixtures("isolated_index_settings")


def test_update_python_parses_index_file_names(bump: Bump) -> None:
    raw_html = """
    <html>
    <body>
    <a>A-B-1.0.4rc1.tar.bz2</a>
    <a>A-B-1.0.1.tar.bz2</a>
    <a>A-B-1.0.0.tar.gz</a>
    <a>A_B-1.0.3-py3-none-any.whl</a>
    <a>A-B-1.0.2.zip<span></a>
    <a>A-B.ok</a>
    <a>A-B-1.sdf.ok</a>
    <a/>
    </body></html>
    """

    assert (
        bump(
            "A-B",
            {"https://I.com/a-b/": httpx.Response(200, text=raw_html)},
            pre_release=False,
            requires_python=None,
            exclude_newer=None,
        )
        == "A-B>=1.0.3"
    )


def test_update_python_accepts_release_without_requires_python(bump: Bump) -> None:

    assert (
        bump(
            "A",
            {"https://I.com/a/": httpx.Response(200, text="<a>A-2.tar.gz</a>")},
            requires_python=">=3.9",
            pre_release=False,
            exclude_newer=None,
        )
        == "A>=2"
    )


def test_update_python_skips_files_of_other_projects(bump: Bump) -> None:
    files = "<a>foo-2.0.tar.gz</a><a>foo_bar-9.0.tar.gz</a><a>foo.bar-8.0-py3-none-any.whl</a><a>foo-bar-7.tar.bz2</a>"

    assert (
        bump(
            "foo>=1",
            {"https://I.com/foo/": httpx.Response(200, text=files)},
            pre_release=False,
            requires_python=None,
            exclude_newer=None,
        )
        == "foo>=2"
    )


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param(
            "text/html",
            """
            <a>A-1.tar.gz</a>
            <a data-requires-python="&gt;=3.6.*">A-2.tar.gz</a>
            <a data-requires-python="&gt;=3.12">A-3.tar.gz</a>
            <a data-yanked="broken">A-4.tar.gz</a>
            """,
            id="html",
        ),
        pytest.param(
            "application/vnd.pypi.simple.v1+json",
            json.dumps({
                "meta": {"api-version": "1.1"},
                "name": "a",
                "files": [
                    {"filename": "a-1.tar.gz", "yanked": False},
                    {"filename": "a-2.tar.gz", "requires-python": ">=3.6.*"},
                    {"filename": "a-3.tar.gz", "requires-python": ">=3.12"},
                    {"filename": "a-4.tar.gz", "yanked": "broken"},
                ],
            }),
            id="json",
        ),
    ],
)
def test_update_python_filters_files(content_type: str, body: str, bump: Bump) -> None:

    assert (
        bump(
            "A",
            {"https://I.com/a/": httpx.Response(200, headers={"Content-Type": content_type}, text=body)},
            requires_python=">=3.11",
            pre_release=False,
            exclude_newer=None,
        )
        == "A>=2"
    )


def test_update_python_skips_malformed_json_files(bump: Bump) -> None:

    assert (
        bump(
            "a",
            {
                "https://I.com/a/": httpx.Response(
                    200,
                    headers={"Content-Type": "application/vnd.pypi.simple.v1+json"},
                    json={"files": [{"filename": 5}, "a-3.tar.gz", {"filename": "a-2.tar.gz", "requires-python": 3}]},
                )
            },
            pre_release=False,
            requires_python=None,
            exclude_newer=None,
        )
        == "a>=2"
    )


@pytest.mark.parametrize(
    ("extra_status", "raised"),
    [
        pytest.param(404, "Client error '404 Not Found' for url 'https://i.com/a/'", id="missing-everywhere"),
        pytest.param(500, "Server error '500 Internal Server Error' for url 'https://e.com/a/'", id="extra-fails"),
    ],
)
def test_update_python_reports_index_errors(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    bump: Bump,
    extra_status: int,
    raised: str,
) -> None:
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://E.com")

    with pytest.raises(SystemExit):
        bump(
            "A",
            {"https://I.com/a/": httpx.Response(404), "https://E.com/a/": httpx.Response(extra_status)},
            pre_release=False,
            requires_python=None,
            exclude_newer=None,
        )

    assert capsys.readouterr().err.startswith(f'failed to look up A, so it was not updated: HTTPStatusError("{raised}')


_CUTOFF: Final[str] = "2026-11-01T00:00:00Z"


@pytest.mark.parametrize(
    ("spec", "files", "exclude_newer", "result"),
    [
        pytest.param(
            "A",
            [("A-1.0.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-2.0.tar.gz", "2026-11-02T09:00:00Z")],
            None,
            "A>=2",
            id="no-cutoff-takes-newest",
        ),
        pytest.param(
            "A",
            [("A-1.0.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-2.0.tar.gz", "2026-11-02T09:00:00Z")],
            _CUTOFF,
            "A>=1",
            id="too-new-release-skipped",
        ),
        pytest.param(
            "A",
            [
                ("A-1.0.tar.gz", "2026-10-20T10:00:00.000000Z"),
                ("A-2.0-py3-none-any.whl", "2026-11-02T09:00:00Z"),
                ("A-2.0.tar.gz", "2026-10-30T10:00:00Z"),
            ],
            _CUTOFF,
            "A>=2",
            id="earliest-file-dates-the-version",
        ),
        pytest.param("A", [("A-2.0.tar.gz", "2026-11-02T09:00:00Z")], _CUTOFF, "A", id="only-too-new-release"),
        pytest.param(
            "A",
            [("A-1.0.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-2.0.tar.gz", None)],
            _CUTOFF,
            "A>=1",
            id="missing-upload-time-skipped",
        ),
        pytest.param(
            "A",
            [("A-1.0.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-2.0.tar.gz", "2026-11-02")],
            _CUTOFF,
            "A>=1",
            id="offset-less-upload-time-skipped",
        ),
        pytest.param("A", [("A-2.0.tar.gz", None)], _CUTOFF, "A", id="no-upload-times"),
        pytest.param(
            "A>=2.0",
            [("A-2.5.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-3.0.tar.gz", "2026-11-02T09:00:00Z")],
            _CUTOFF,
            "A>=2.5",
            id="floor-moves",
        ),
        pytest.param(
            "A>=2.5",
            [("A-2.4.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-3.0.tar.gz", "2026-11-02T09:00:00Z")],
            _CUTOFF,
            "A>=2.5",
            id="floor-above-eligible-kept",
        ),
        pytest.param(
            "A>=2.5",
            [("A-2.5.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-3.0.tar.gz", "2026-11-02T09:00:00Z")],
            _CUTOFF,
            "A>=2.5",
            id="floor-at-eligible-kept",
        ),
        pytest.param(
            "A==2.5",
            [("A-2.4.tar.gz", "2026-10-20T10:00:00.000000Z"), ("A-2.6.tar.gz", "2026-11-02T09:00:00Z")],
            _CUTOFF,
            "A==2.5",
            id="pin-above-eligible-kept",
        ),
    ],
)
def test_update_python_respects_upload_cutoff(
    spec: str, files: list[tuple[str, str | None]], exclude_newer: str | None, result: str, bump: Bump
) -> None:
    entries = [{"filename": name, "upload-time": uploaded} for name, uploaded in files]
    response = httpx.Response(
        200, json={"files": entries}, headers={"content-type": "application/vnd.pypi.simple.v1+json"}
    )

    assert (
        bump(spec, {"https://I.com/a/": response}, exclude_newer=exclude_newer, pre_release=False, requires_python=None)
        == result
    )


@pytest.mark.parametrize(
    ("exclude_newer", "result"),
    [
        pytest.param(None, "A>=2", id="no-cutoff"),
        pytest.param(_CUTOFF, "A>=1", id="cutoff-has-no-upload-times"),
    ],
)
def test_update_python_html_index_has_no_upload_times(exclude_newer: str | None, result: str, bump: Bump) -> None:
    html = "<a>A-1.tar.gz</a><a>A-2.tar.gz</a>"

    assert (
        bump(
            "A>=1",
            {"https://I.com/a/": httpx.Response(200, text=html)},
            exclude_newer=exclude_newer,
            pre_release=False,
            requires_python=None,
        )
        == result
    )

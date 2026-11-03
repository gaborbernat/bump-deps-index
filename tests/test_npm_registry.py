from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx
import pytest

from bump_deps_index import main

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_httpx import HTTPXMock

pytestmark = pytest.mark.usefixtures("isolated_index_settings")


_CUTOFF: Final[str] = "2026-11-01T00:00:00Z"


def test_update_js_encodes_scoped_package(bump: Callable[..., str]) -> None:

    assert (
        bump(
            "@scope/package", {"https://N.com/@scope%2Fpackage": httpx.Response(200, json={"versions": {"1.0.0": {}}})}
        )
        == "@scope/package@1.0.0"
    )


def test_update_js_requests_abbreviated_metadata_and_skips_deprecated(
    httpx_mock: HTTPXMock, bump: Callable[..., str]
) -> None:
    httpx_mock.add_response(
        url="https://N.com/a",
        match_headers={"Accept": "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8"},
        json={"versions": {"1.0.0": {}, "2.0.0": {"deprecated": "broken"}}},
    )

    assert bump("a@", {}) == "a@1.0.0"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"versions": None}, id="null-versions"),
        pytest.param({"versions": ["1.0.0"]}, id="list-versions"),
        pytest.param(["1.0.0"], id="list-payload"),
    ],
)
def test_update_js_rejects_malformed_metadata(
    capsys: pytest.CaptureFixture[str], bump: Callable[..., str], payload: dict[str, list[str] | None] | list[str]
) -> None:

    with pytest.raises(SystemExit):
        bump("a@", {"https://N.com/a": httpx.Response(200, json=payload)})

    assert (
        capsys.readouterr().err
        == "failed to look up a@, so it was not updated: TypeError('https://n.com/a has no versions dict')\n"
    )


def test_update_js_skips_malformed_version_metadata(bump: Callable[..., str]) -> None:

    assert (
        bump(
            "a@",
            {"https://N.com/a": httpx.Response(200, json={"versions": {"1.0.0": "x", "2.0.0": {"deprecated": "y"}}})},
        )
        == "a@1.0.0"
    )


@pytest.mark.parametrize(
    ("spec", "uploads", "latest", "result"),
    [
        pytest.param(
            "a@",
            {"1.0.0": "2026-10-20T10:00:00.000000Z", "2.0.0": "2026-11-02T09:00:00Z"},
            "2.0.0",
            "a@1.0.0",
            id="latest-too-new",
        ),
        pytest.param(
            "a@^2.0.0",
            {
                "2.0.0": "2026-10-20T10:00:00.000000Z",
                "2.5.0": "2026-10-20T10:00:00.000000Z",
                "2.9.0": "2026-11-02T09:00:00Z",
            },
            "2.9.0",
            "a@^2.5.0",
            id="range-skips-too-new",
        ),
        pytest.param(
            "a@^1.0.0",
            {
                "1.0.0": "2026-10-20T10:00:00.000000Z",
                "1.2.0": "2026-10-20T10:00:00.000000Z",
                "2.0.0": "2026-11-02T09:00:00Z",
            },
            "2.0.0",
            "a@^1.2.0",
            id="caret",
        ),
        pytest.param(
            "a@1.0.0",
            {"1.0.0": "2026-10-20T10:00:00.000000Z", "1.1.0": None},
            "1.1.0",
            "a@1.0.0",
            id="missing-upload-time-skipped",
        ),
        pytest.param(
            "a@",
            {"1.0.0": "2026-10-20T10:00:00.000000Z", "2.0.0": None},
            "2.0.0",
            "a@1.0.0",
            id="version-without-upload-time",
        ),
        pytest.param(
            "a@>=2.5.0",
            {"2.4.0": "2026-10-20T10:00:00.000000Z", "3.0.0": "2026-11-02T09:00:00Z"},
            "3.0.0",
            "a@>=2.5.0",
            id="floor-above-eligible-kept",
        ),
        pytest.param(
            "a@^2.5.0",
            {"2.4.0": "2026-10-20T10:00:00.000000Z", "3.0.0": "2026-11-02T09:00:00Z"},
            "3.0.0",
            "a@^2.5.0",
            id="caret-above-eligible-kept",
        ),
        pytest.param(
            "a@2.5.0",
            {"2.4.0": "2026-10-20T10:00:00.000000Z", "2.6.0": "2026-11-02T09:00:00Z"},
            "2.6.0",
            "a@2.5.0",
            id="pin-above-eligible-kept",
        ),
    ],
)
def test_update_js_respects_upload_cutoff(
    spec: str, uploads: dict[str, str | None], latest: str, result: str, bump: Callable[..., str]
) -> None:
    times = {version: uploaded for version, uploaded in uploads.items() if uploaded is not None}
    document = {"versions": {version: {} for version in uploads}, "time": times, "dist-tags": {"latest": latest}}

    assert bump(spec, {"https://N.com/a": httpx.Response(200, json=document)}, exclude_newer=_CUTOFF) == result


def test_update_js_without_time_map_offers_no_candidates(bump: Callable[..., str]) -> None:
    response = httpx.Response(200, json={"versions": {"1.0.0": {}}, "dist-tags": {"latest": "1.0.0"}})

    assert bump("a@", {"https://N.com/a": response}, exclude_newer=_CUTOFF) == "a@"


def test_npm_package_listed_twice_is_fetched_once(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="https://N.com/a", json={"versions": {"1.0.0": {}, "2.0.0": {}}, "dist-tags": {"latest": "2.0.0"}}
    )

    main(["-i", "https://I.com", "-n", "https://N.com", "a@^1.0.0", "a@^2.0.0"])

    assert len(httpx_mock.get_requests()) == 1

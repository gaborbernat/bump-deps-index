from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx
import pytest

if TYPE_CHECKING:
    from conftest import Bump


pytestmark: Final[pytest.MarkDecorator] = pytest.mark.usefixtures("isolated_index_settings")


@pytest.mark.parametrize(
    ("spec", "versions", "pre_release", "result"),
    [
        pytest.param("a@1", ["1.0.0", "2.0.0"], False, "a@2.0.0", id="versioned"),
        pytest.param("a@", ["2.0.0"], False, "a@2.0.0", id="bare"),
        pytest.param("a@", ["1.0.0", "1.1.0", "bad", "1.2.0-a.1"], False, "a@1.1.0", id="skip-invalid-and-pre"),
        pytest.param("a@", ["1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1"], True, "a@1.0.0-rc.1", id="pre-rc"),
        pytest.param("a@", ["1.0.0-beta.2", "1.0.0-beta.11"], True, "a@1.0.0-beta.11", id="pre-numeric-order"),
        pytest.param("a@v1.0.0", ["1.0.0", "2.0.0"], False, "a@2.0.0", id="v-prefixed-pin"),
        pytest.param("a@^1.0.0", ["1.0.0", "1.2.0", "2.0.0"], False, "a@^1.2.0", id="caret-keeps-major"),
        pytest.param("a@^0.2.0", ["0.2.0", "0.2.5", "0.3.0"], False, "a@^0.2.5", id="caret-zero-major-keeps-minor"),
        pytest.param("a@^0.0.1", ["0.0.1", "0.0.2"], False, "a@^0.0.1", id="caret-zero-minor-keeps-patch"),
        pytest.param("a@~1.2.0", ["1.2.0", "1.2.3", "1.3.0"], False, "a@~1.2.3", id="tilde-keeps-minor"),
        pytest.param("a@>=1.0.0", ["1.0.0", "2.0.0"], False, "a@>=2.0.0", id="lower-bound"),
        pytest.param("a@^2.0.0", ["1.0.0"], False, "a@^2.0.0", id="no-release-in-range"),
        pytest.param("a@<2", ["1.0.0"], False, "a@<2", id="unsupported-operator"),
        pytest.param("a@^1.x", ["1.0.0"], False, "a@^1.x", id="unsupported-version"),
        pytest.param("a@latest", ["1.0.0"], False, "a@latest", id="dist-tag"),
        pytest.param("a@1.2", ["1.0.0", "2.0.0"], False, "a@2.0.0", id="partial-pin"),
        pytest.param("a@1 || 2", ["1.0.0", "3.0.0"], False, "a@1 || 2", id="union-range"),
        pytest.param("a@2.0.0-beta.1", ["1.9.0", "2.0.0-beta.1"], False, "a@2.0.0-beta.1", id="pin-no-downgrade"),
        pytest.param("a@3", ["2.0.0"], False, "a@3", id="partial-pin-no-downgrade"),
        pytest.param("a@1.0.0", ["1.1.0-beta"], False, "a@1.0.0", id="only-pre-releases"),
        pytest.param("a@1.x", ["1.0.0", "2.0.0"], False, "a@1.x", id="x-range"),
    ],
)
def test_update_js(spec: str, versions: list[str], *, pre_release: bool, result: str, bump: Bump) -> None:

    assert (
        bump(
            spec,
            {"https://N.com/a": httpx.Response(200, json={"versions": {key: {} for key in versions}})},
            pre_release=pre_release,
            requires_python=None,
            exclude_newer=None,
        )
        == result
    )


@pytest.mark.parametrize(
    ("spec", "result"),
    [
        pytest.param("a@", "a@1.4.0", id="bare"),
        pytest.param("a@1.0.0", "a@1.4.0", id="pin"),
        pytest.param("a@^1.0.0", "a@^1.4.0", id="range"),
        pytest.param("a@^1.5.0", "a@^1.5.0", id="range-above-latest"),
        pytest.param("a@~1.0.0", "a@~1.0.0", id="range-below-latest"),
    ],
)
def test_update_js_prefers_latest_tag_inside_range(spec: str, result: str, bump: Bump) -> None:
    versions = {key: {} for key in ("1.0.0", "1.4.0", "1.5.0", "2.0.0")}

    assert (
        bump(
            spec,
            {"https://N.com/a": httpx.Response(200, json={"dist-tags": {"latest": "1.4.0"}, "versions": versions})},
            pre_release=False,
            requires_python=None,
            exclude_newer=None,
        )
        == result
    )

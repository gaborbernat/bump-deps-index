from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx
import pytest

if TYPE_CHECKING:
    from conftest import Bump
    from pytest_httpx import HTTPXMock

pytestmark: Final[pytest.MarkDecorator] = pytest.mark.usefixtures("isolated_index_settings")


@pytest.mark.parametrize(
    ("spec", "pre_release", "versions", "result"),
    [
        pytest.param("A", False, ["1.0.0"], "A>=1", id="no-ver"),
        pytest.param("A==1", False, ["1.1"], "A==1.1", id="eq-ver"),
        pytest.param("A===1", False, ["2"], "A===2", id="arbitrary-equality"),
        pytest.param("A<1", False, ["1.1"], "A<1", id="lt-ver"),
        pytest.param("A<2", False, ["1.5"], "A<2,>=1.5", id="preserve-upper-bound"),
        pytest.param("A (<2)", False, ["1.5"], "A (<2,>=1.5)", id="parenthesized-bound"),
        pytest.param("A <2 ; os_name=='nt'", False, ["1.5"], "A <2,>=1.5 ; os_name=='nt'", id="bound-marker"),
        pytest.param(
            "A[ b , a ] ;python_version<'3.99'",
            False,
            ["1"],
            "A[ b , a ]>=1 ;python_version<'3.99'",
            id="keeps-extras-and-marker-format",
        ),
        pytest.param(
            'A; python_version<"3.11"',
            False,
            ["1"],
            'A>=1; python_version<"3.11"',
            id="py-ver-marker",
        ),
        pytest.param(
            "A; python_version<'3.11'",
            False,
            ["1"],
            "A>=1; python_version<'3.11'",
            id="py-ver-marker-single-quote",
        ),
        pytest.param(
            'A[X]; python_version<"3.11"',
            False,
            ["1"],
            'A[X]>=1; python_version<"3.11"',
            id="py-ver-marker-extra",
        ),
        pytest.param(
            "A>=1",
            True,
            ["1.2.0b2", "1.2.0b1", "1.1.0", "0.1.0"],
            "A>=1.2.0b2",
            id="pre-release",
        ),
        pytest.param(
            "A",
            False,
            ["1.1.0+b2", "1.1.0+b1", "1.1.0", "0.1.0"],
            "A>=1.1",
            id="ignore-build-marker",
        ),
        pytest.param(
            "A @ https://example.com/a.whl",
            False,
            [],
            "A @ https://example.com/a.whl",
            id="direct-reference",
        ),
        pytest.param("A==2.0b1", False, ["1.9"], "A==2.0b1", id="eq-no-downgrade"),
        pytest.param("A==1.*", False, ["2.5"], "A==2.*", id="eq-wildcard"),
        pytest.param("A==1.4.*", False, ["2.5.1"], "A==2.5.*", id="eq-wildcard-depth"),
        pytest.param("A==1.4.*", False, ["3"], "A==3.0.*", id="eq-wildcard-pad"),
        pytest.param("A==1.4.*", False, ["1.4.9"], "A==1.4.*", id="eq-wildcard-same"),
        pytest.param("A==2.*", False, ["1.9"], "A==2.*", id="eq-wildcard-no-downgrade"),
        pytest.param("A==1!1.*", False, ["1!2.5"], "A==1!2.*", id="eq-wildcard-epoch"),
        pytest.param("A===2.0.0", False, ["3.0.0"], "A===3.0.0", id="arbitrary-equality-verbatim"),
        pytest.param("A===2.0.0", False, ["2.0.0"], "A===2.0.0", id="arbitrary-equality-same"),
        pytest.param("A===foo", False, ["1"], "A===1", id="arbitrary-equality-not-pep440"),
        pytest.param("A~=1.4", False, ["2.1", "1.9.3"], "A~=1.9", id="compatible-release"),
        pytest.param("A~=2.0", False, ["2.0.5"], "A~=2.0", id="compatible-release-same"),
        pytest.param("A~=1.4.2", False, ["1.4.7"], "A~=1.4.7", id="compatible-release-precision"),
        pytest.param("A~=1.4.2", False, ["1.5", "1.4.9"], "A~=1.4.9", id="compatible-release-cap"),
        pytest.param("A~=1.4", True, ["1.9b1"], "A~=1.9b1", id="compatible-release-pre"),
        pytest.param("A~=1!1.4", False, ["1!1.9.3"], "A~=1!1.9", id="compatible-release-epoch"),
        pytest.param("A >= 1.0", False, ["1.0"], "A >= 1.0", id="unchanged-keeps-format"),
        pytest.param("A >= 1.0 , <3", False, ["2.5"], "A >= 2.5 , <3", id="keeps-format"),
        pytest.param("A>=1.2,!=1.2.5,<3", False, ["1.9"], "A>=1.9,!=1.2.5,<3", id="keeps-order"),
        pytest.param("A>=1.2,<=1.2.5", False, ["1.2.4"], "A>=1.2.4,<=1.2.5", id="no-substring-match"),
        pytest.param("A==1.0,<3", False, ["3.0", "2.5"], "A==2.5,<3", id="eq-inside-upper-bound"),
        pytest.param("A==1.0,<2", False, ["2.1", "1.0"], "A==1.0,<2", id="eq-upper-bound-same"),
        pytest.param("A==1.*,!=2.*", False, ["2.1"], "A==1.*,!=2.*", id="eq-wildcard-excluded"),
        pytest.param("A==1.0+cpu", False, ["1.0+cu118", "1.0+cpu"], "A==1.0+cpu", id="eq-local"),
        pytest.param("A==1.0+cpu", False, ["2.0+cu118", "2.0+cpu"], "A==2+cpu", id="eq-local-newer"),
    ],
)
def test_update_python(spec: str, *, pre_release: bool, versions: list[str], result: str, bump: Bump) -> None:
    page = "".join(f"<a>A-{version}.tar.gz</a>" for version in versions)

    assert (
        bump(
            spec,
            {"https://I.com/a/": httpx.Response(200, text=page)},
            pre_release=pre_release,
            requires_python=None,
            exclude_newer=None,
        )
        == result
    )


def test_update_python_url_requirement_reads_no_index(bump: Bump, httpx_mock: HTTPXMock) -> None:
    bump("A @ https://example.com/a.whl", {}, pre_release=False, requires_python=None, exclude_newer=None)

    assert httpx_mock.get_requests() == []

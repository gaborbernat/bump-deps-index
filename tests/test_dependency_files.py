from __future__ import annotations

import os
import time
from textwrap import dedent
from threading import Event
from typing import TYPE_CHECKING

import pytest
from conftest import FakeIndex

if TYPE_CHECKING:
    from pathlib import Path

    import httpx
    from pytest_httpx import HTTPXMock


def test_requirements_preserves_comments_and_similar_names(tmp_path: Path, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo  # keep this reason\nfoobar\n", encoding="utf-8")
    index.pypi["foo"] = ["2"]
    index.pypi["foobar"] = ["3"]

    assert index.run(requirements)

    assert requirements.read_text(encoding="utf-8") == "foo>=2  # keep this reason\nfoobar>=3\n"


def test_pyproject_updates_only_dependency_tables(tmp_path: Path, index: FakeIndex) -> None:
    pyproject = tmp_path / "pyproject.toml"
    content = """
    [project]
    name = "example"

    [project.optional-dependencies]
    test = ["foo"]

    [tool.example]
    dependencies = ["foo"]
    """
    pyproject.write_text(dedent(content).lstrip(), encoding="utf-8")
    index.pypi["foo"] = ["2"]

    assert index.run(pyproject)

    expected = dedent(content).lstrip().replace('test = ["foo"]', 'test = ["foo>=2"]')
    assert pyproject.read_text(encoding="utf-8") == expected


def test_setup_cfg_updates_only_requirement_values(tmp_path: Path, index: FakeIndex) -> None:
    setup_cfg = tmp_path / "setup.cfg"
    setup_cfg.write_text(
        dedent(
            """
            [options]
            packages = foo
            python_requires = >=3.11
            install_requires =
                foo
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi["foo"] = ["2"]

    assert index.run(setup_cfg)

    assert (
        setup_cfg.read_text(encoding="utf-8")
        == dedent(
            """
        [options]
        packages = foo
        python_requires = >=3.11
        install_requires =
            foo>=2
        """
        ).lstrip()
    )


def test_tox_ini_preserves_commands_and_factors(tmp_path: Path, index: FakeIndex) -> None:
    tox_ini = tmp_path / "tox.ini"
    tox_ini.write_text(
        dedent(
            """
            [testenv]
            deps =
                py311: foo
            commands = foo
            """
        ).lstrip(),
        encoding="utf-8",
    )
    index.pypi["foo"] = ["2"]

    assert index.run(tox_ini)

    assert (
        tox_ini.read_text(encoding="utf-8")
        == dedent(
            """
        [testenv]
        deps =
            py311: foo>=2
        commands = foo
        """
        ).lstrip()
    )


def test_pre_commit_preserves_repository_urls(tmp_path: Path, index: FakeIndex) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    content = """
    repos:
      - repo: https://example.com/foo
        hooks:
          - id: foo
            additional_dependencies:
              - foo
    """
    config.write_text(dedent(content).lstrip(), encoding="utf-8")
    index.pypi["foo"] = ["2"]

    assert index.run(config)

    assert config.read_text(encoding="utf-8") == dedent(content).lstrip().replace("- foo\n", "- foo>=2\n")


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        pytest.param(
            "tox.ini",
            """
            [tox]
            requires = foo
            [testenv]
            deps = foo>=1  # why
            [testenv:url]
            deps =
                bar @ git+https://github.com/a/bar
                py311, !pypy: foo>=1
            """,
            """
            [tox]
            requires = foo>=2
            [testenv]
            deps = foo>=2  # why
            [testenv:url]
            deps =
                bar @ git+https://github.com/a/bar
                py311, !pypy: foo>=2
            """,
            id="tox-ini-single-line-and-url",
        ),
        pytest.param(
            "setup.cfg",
            """
            [options]
            install_requires = foo>=1
            [options.extras_require]
            test = foo
            """,
            """
            [options]
            install_requires = foo>=2
            [options.extras_require]
            test = foo>=2
            """,
            id="setup-cfg-single-line",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            optional-dependencies = { test = ["foo>=1"] }
            """,
            """
            [project]
            name = "demo"
            optional-dependencies = { test = ["foo>=2"] }
            """,
            id="pyproject-inline-table",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "my-pkg"
            dependencies = ["My_Pkg[x]>=1", "foo>=1"]
            """,
            """
            [project]
            name = "my-pkg"
            dependencies = ["My_Pkg[x]>=1", "foo>=2"]
            """,
            id="pyproject-skips-own-non-canonical-name",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = [
              "foo>=1",  # see [docs
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            dependencies = [
              "foo>=2",  # see [docs
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            id="pyproject-bracket-in-comment",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = ["  foo>=1 "]
            """,
            """
            [project]
            name = "demo"
            dependencies = ["  foo>=2 "]
            """,
            id="pyproject-padded-spec",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            dependencies = [
              "not \\"]\\" valid",
              "foo>=1",
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            dependencies = [
              "not \\"]\\" valid",
              "foo>=2",
            ]
            [tool.other]
            pins = ["foo>=1"]
            """,
            id="pyproject-bracket-in-string",
        ),
        pytest.param(
            "tox.toml",
            """
            [env_run_base]
            deps = [
              "foo>=1",  # see [docs
            ]
            [env_run_base.set_env]
            PINNED = "foo>=1"
            """,
            """
            [env_run_base]
            deps = [
              "foo>=2",  # see [docs
            ]
            [env_run_base.set_env]
            PINNED = "foo>=1"
            """,
            id="tox-toml-bracket-in-comment",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - additional_dependencies:
                      - foo>=1
                    id: block
                  - additional_dependencies: [foo>=1]
                    id: flow
                  - id: other
                    args: [foo>=1]
            """,
            """
            repos:
              - repo: local
                hooks:
                  - additional_dependencies:
                      - foo>=2
                    id: block
                  - additional_dependencies: [foo>=2]
                    id: flow
                  - id: other
                    args: [foo>=1]
            """,
            id="pre-commit-dependencies-first-key",
        ),
        pytest.param(
            ".pre-commit-config.yaml",
            """
            repos:
              - repo: local
                hooks:
                  - id: lint
                    additional_dependencies: [
                      "foo>=1",
                      foo>=1,  # why
                      foo>=1
                    ]
                    args: [foo>=1]
            """,
            """
            repos:
              - repo: local
                hooks:
                  - id: lint
                    additional_dependencies: [
                      "foo>=2",
                      foo>=2,  # why
                      foo>=2
                    ]
                    args: [foo>=1]
            """,
            id="pre-commit-multi-line-flow",
        ),
        pytest.param(
            "tox.ini",
            """
            [testenv]
            deps: foo>=1
            [testenv:b]
            deps =
                # pinned: see issue
                foo>=1
            commands: foo>=1
            """,
            """
            [testenv]
            deps: foo>=2
            [testenv:b]
            deps =
                # pinned: see issue
                foo>=2
            commands: foo>=1
            """,
            id="tox-ini-colon-delimiter",
        ),
        pytest.param(
            "setup.cfg",
            """
            [options]
            install_requires: foo>=1
            """,
            """
            [options]
            install_requires: foo>=2
            """,
            id="setup-cfg-colon-delimiter",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [ project ]
            name = "demo"
            dependencies = ["foo>=1"]
            [ "project" . optional-dependencies ]
            test = ["foo>=1"]
            """,
            """
            [ project ]
            name = "demo"
            dependencies = ["foo>=2"]
            [ "project" . optional-dependencies ]
            test = ["foo>=2"]
            """,
            id="pyproject-spaced-table-header",
        ),
        pytest.param(
            "pyproject.toml",
            """
            project.name = "demo"
            project.dependencies = ["foo>=1"]
            tool.other.pins = ["foo>=1"]
            """,
            """
            project.name = "demo"
            project.dependencies = ["foo>=2"]
            tool.other.pins = ["foo>=1"]
            """,
            id="pyproject-top-level-dotted-key",
        ),
        pytest.param(
            "pyproject.toml",
            """
            [project]
            name = "demo"
            [tool.uv]
            dev-dependencies = ["foo>=1"]
            """,
            """
            [project]
            name = "demo"
            [tool.uv]
            dev-dependencies = ["foo>=2"]
            """,
            id="pyproject-uv-dev-dependencies",
        ),
        pytest.param(
            "tox.toml",
            """
            env.test.deps = ["foo>=1"]
            env.test.commands = [["foo>=1"]]
            """,
            """
            env.test.deps = ["foo>=2"]
            env.test.commands = [["foo>=1"]]
            """,
            id="tox-toml-dotted-key",
        ),
        pytest.param(
            "package.json",
            """
            {
              "dependencies": {"foo": "^1.0.0", "bar": "file:../bar", "baz": "github:a/baz"},
              "devDependencies": {
                "foo": "~1.0.0"
              },
              "peerDependencies": {"foo": "^1.0.0"},
              "scripts": {"foo": "^1.0.0"}
            }
            """,
            """
            {
              "dependencies": {"foo": "^1.5.0", "bar": "file:../bar", "baz": "github:a/baz"},
              "devDependencies": {
                "foo": "~1.0.5"
              },
              "peerDependencies": {"foo": "^1.0.0"},
              "scripts": {"foo": "^1.0.0"}
            }
            """,
            id="package-json",
        ),
        pytest.param("package.json", "[]\n", "[]\n", id="package-json-not-an-object"),
        pytest.param(
            "package.json",
            """
            {
              "overrides": {"x": {"dependencies": {"foo": "^1.0.0"}}},
              "description": "a } brace and a \\" quote",
              "dependencies": {"foo": "^1.0.0"}
            }
            """,
            """
            {
              "overrides": {"x": {"dependencies": {"foo": "^1.0.0"}}},
              "description": "a } brace and a \\" quote",
              "dependencies": {"foo": "^1.5.0"}
            }
            """,
            id="package-json-top-level-only",
        ),
        pytest.param(
            "pyproject.toml",
            '''
            [project]
            name = "demo"
            readme.text = """
            dependencies = ["foo>=1"]
            """
            version = """1"""
            dependencies = ["foo>=1"]
            ''',
            '''
            [project]
            name = "demo"
            readme.text = """
            dependencies = ["foo>=1"]
            """
            version = """1"""
            dependencies = ["foo>=2"]
            ''',
            id="pyproject-multi-line-string",
        ),
        pytest.param("dev-requirements.txt", "foo>=1\n", "foo>=2\n", id="requirements-any-name"),
    ],
)
@pytest.mark.usefixtures("foo_index")
def test_file_updates(tmp_path: Path, index: FakeIndex, name: str, content: str, expected: str) -> None:
    dest = tmp_path / name
    dest.write_text(dedent(content).lstrip(), encoding="utf-8")

    assert index.run(dest)

    assert dest.read_text(encoding="utf-8") == dedent(expected).lstrip()


@pytest.mark.usefixtures("foo_index")
def test_requirements_preserves_crlf_line_endings(tmp_path: Path, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_bytes(b"foo>=1\r\nbar>=1\r\n")
    index.pypi["bar"] = ["1"]

    assert index.run(requirements)

    assert requirements.read_bytes() == b"foo>=2\r\nbar>=1\r\n"


@pytest.mark.usefixtures("foo_index")
def test_unchanged_file_is_not_rewritten(tmp_path: Path, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo>=2\n", encoding="utf-8")
    os.utime(requirements, ns=(0, 0))

    assert index.run(requirements)

    assert requirements.stat().st_mtime_ns == 0


@pytest.mark.usefixtures("foo_index")
def test_package_shared_across_files_is_fetched_once(tmp_path: Path, httpx_mock: HTTPXMock, index: FakeIndex) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo>=1\n", encoding="utf-8")
    tox_toml = tmp_path / "tox.toml"
    tox_toml.write_text('[env_run_base]\ndeps = ["foo>=1", "foo>=1.5"]\n', encoding="utf-8")

    assert index.run(requirements, tox_toml)

    assert (requirements.read_text(encoding="utf-8"), tox_toml.read_text(encoding="utf-8")) == (
        "foo>=2\n",
        '[env_run_base]\ndeps = ["foo>=2", "foo>=2"]\n',
    )
    assert len(httpx_mock.get_requests()) == 1


def test_output_follows_file_order(capsys: pytest.CaptureFixture[str], tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    fake = FakeIndex(pypi={"a": ["2"], "b": ["2"]})
    b_served = Event()

    def serve(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/a/"):
            b_served.wait(timeout=5)  # answer `a` last to finish its lookup after `b`
            time.sleep(0.05)
        response = fake.serve(request)
        b_served.set()
        return response

    httpx_mock.add_callback(serve, is_reusable=True)
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("a\nb\n", encoding="utf-8")

    assert fake.run(requirements)

    assert capsys.readouterr().out.splitlines() == [
        "Using Python index: https://pypi.example/simple",
        "a -> a>=2",
        "b -> b>=2",
    ]


def test_requires_python_comes_from_nearest_pyproject(tmp_path: Path, index: FakeIndex) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.9"\n')
    (tmp_path / "requirements").mkdir()
    requirements = tmp_path / "requirements" / "requirements-dev.txt"
    requirements.write_text("foo\n", encoding="utf-8")
    index.pypi["foo"] = ["1", "2"]
    index.requires_python["foo-2.tar.gz"] = ">=3.10"

    assert index.run(requirements)

    assert requirements.read_text(encoding="utf-8") == "foo>=1\n"


def test_failure_message_redacts_index_credentials(
    tmp_path: Path, index: FakeIndex, capsys: pytest.CaptureFixture[str]
) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("foo\n", encoding="utf-8")
    index.index_url = "https://user:s3cret@pypi.example/simple"

    assert not index.run(requirements)

    err = capsys.readouterr().err
    assert "https://pypi.example/simple/foo/" in err
    assert "s3cret" not in err


def test_output_redacts_direct_reference_credentials(
    tmp_path: Path, index: FakeIndex, capsys: pytest.CaptureFixture[str]
) -> None:
    requirements = tmp_path / "requirements.txt"
    content = "foo @ https://user:s3cret@files.example/foo-1.0-py3-none-any.whl\n"
    requirements.write_text(content, encoding="utf-8")

    assert index.run(requirements)

    assert (capsys.readouterr().out.splitlines(), requirements.read_text(encoding="utf-8")) == (
        ["Using Python index: https://pypi.example/simple", "foo @ https://files.example/foo-1.0-py3-none-any.whl"],
        content,
    )


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        pytest.param(
            "tox.ini",
            f"[testenv]\ndeps =\n    {'!,' * 26}x\n    foo>=1\n",
            f"[testenv]\ndeps =\n    {'!,' * 26}x\n    foo>=2\n",
            id="tox-ini-factor-like-commas",
        ),
        pytest.param(
            "pyproject.toml",
            f'[project]\nname = "demo"\ndependencies = [\n  "foo"{" " * 100_000},\n]\n',
            f'[project]\nname = "demo"\ndependencies = [\n  "foo>=2"{" " * 100_000},\n]\n',
            id="pyproject-long-whitespace",
        ),
    ],
)
@pytest.mark.usefixtures("foo_index")
def test_pathological_line_parses_in_linear_time(
    tmp_path: Path, index: FakeIndex, name: str, content: str, expected: str
) -> None:
    dest = tmp_path / name
    dest.write_text(content, encoding="utf-8")
    start = time.perf_counter()

    assert index.run(dest)

    assert (dest.read_text(encoding="utf-8"), time.perf_counter() - start < 1) == (expected, True)


@pytest.mark.parametrize(
    "name", ["pyproject.toml", "tox.toml", "tox.ini", "setup.cfg", ".pre-commit-config.yaml", "requirements.txt"]
)
def test_empty_file_stays_empty(
    capsys: pytest.CaptureFixture[str], index: FakeIndex, tmp_path: Path, name: str
) -> None:
    dest = tmp_path / name
    dest.write_text("")

    assert index.run(dest)

    assert (*capsys.readouterr(), dest.read_text()) == ("", "", "")


@pytest.fixture
def foo_index(index: FakeIndex) -> None:
    index.pypi["foo"] = ["2"]
    index.npm["foo"] = ["1.0.0", "1.0.5", "1.5.0", "2.0.0"]

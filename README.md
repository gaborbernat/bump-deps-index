# bump-deps-index

[![PyPI](https://img.shields.io/pypi/v/bump-deps-index?style=flat-square)](https://pypi.org/project/bump-deps-index/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/bump-deps-index.svg)](https://pypi.org/project/bump-deps-index/)
[![check](https://github.com/gaborbernat/bump-deps-index/actions/workflows/check.yaml/badge.svg)](https://github.com/gaborbernat/bump-deps-index/actions/workflows/check.yaml)
[![Documentation Status](https://readthedocs.org/projects/bump-deps-index/badge/?version=latest)](https://bump-deps-index.readthedocs.io/en/latest/?badge=latest)
[![Downloads](https://static.pepy.tech/badge/bump-deps-index/month)](https://pepy.tech/project/bump-deps-index)

Update pinned Python and JavaScript dependencies against their package indexes while preserving each file's layout.

## Install

```console
pipx install bump-deps-index
```

## Use

Run the command in a project root to update every supported file it finds:

```console
bump-deps-index
```

Pass package specifications to inspect them without editing files:

```console
bump-deps-index 'httpx>=0.27' prettier@3.0.0
```

Use `--file` to limit updates. Supported inputs include `pyproject.toml`, `tox.toml`, `tox.ini`, `setup.cfg`,
requirements files, `.pre-commit-config.yaml`, and Python scripts with PEP 723 metadata.

When `[project].requires-python` is present in the root `pyproject.toml`, Python updates exclude distributions that do
not support the project's oldest interpreter. Projects without that field keep the index's existing selection behavior.

See the [documentation](https://bump-deps-index.readthedocs.io) for all options.

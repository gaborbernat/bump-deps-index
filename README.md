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

Set `[project].requires-python` in a `pyproject.toml` and you get Python updates from distributions that support the
oldest interpreter you allow there, for files in that directory and its subdirectories. For a PEP 723 script with its
own `requires-python`, you get updates for that range. Without either field, you get the newest release on the index.

For an `==` pin you get a newer release or no change, and you keep wildcards at their depth, so you go from `==1.*` to
`==2.*`. On `~=` bounds you keep the precision you wrote, so you go from `~=1.4` to `~=1.9`. You keep hashed
requirements as you wrote them, since you would need new hashes for a new version.

In `.pre-commit-config.yaml`, you get PyPI updates for `python` hooks and npm updates for `node` hooks, and no updates
for hooks in other languages. You see changes on disk for files with a new version, with their line endings intact.

See the [documentation](https://bump-deps-index.readthedocs.io) for all options.

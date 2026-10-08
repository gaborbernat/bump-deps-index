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
`package.json`, `.pre-commit-config.yaml`, Python scripts with PEP 723 metadata, and requirements files. Without
`--file` you get the `requirements*` and `constraints*` files ending in `.txt` or `.in`; with `--file` you can name any
such file, such as `dev-requirements.txt`.

Without `--index-url` you get the index from `PIP_INDEX_URL`, `UV_DEFAULT_INDEX` or `UV_INDEX_URL`, then the default
index of the nearest `uv.toml` or `[tool.uv]` table, then `index-url` from your pip configuration, then your user
`uv.toml`. For a named uv index you send the credentials from `UV_INDEX_<NAME>_USERNAME` and `UV_INDEX_<NAME>_PASSWORD`.
For a package that `[tool.uv.sources]` of the project or its workspace root pins to an index you get updates from that
index, and for one from git, a path or a URL you keep the spec as you wrote it.

Without `--npm-registry` you get `NPM_CONFIG_REGISTRY`, then `registry` from the `.npmrc` in the working directory, then
from your user `.npmrc`. From those files you also get the `@scope:registry` of a scoped package and the `_authToken` or
`_auth` credentials of each registry.

Set `[project].requires-python` in a `pyproject.toml` and you get Python updates from distributions that support the
oldest interpreter you allow there, for files in that directory and its subdirectories. For a PEP 723 script with its
own `requires-python`, you get updates for that range. Without either field, you get the newest release on the index.

For an `==` pin you get a newer release or no change, and you keep wildcards at their depth, so you go from `==1.*` to
`==2.*`. On `~=` bounds you keep the precision you wrote, so you go from `~=1.4` to `~=1.9`. You keep hashed
requirements as you wrote them, since you would need new hashes for a new version.

On npm ranges you stay inside the range, so `^1.2.0` goes to the newest `1.x` release and `~1.2.0` to the newest
`1.2.x`. You get the newest release for `>=1.2.0` and for a full or partial version, and you keep ranges such as
`1 || 2` or `latest` as you wrote them. In `package.json` you get updates for `dependencies`, `devDependencies` and
`optionalDependencies`.

In `.pre-commit-config.yaml`, you get PyPI updates for `python` hooks and npm updates for `node` hooks, and no updates
for hooks in other languages. For a remote hook without a `language`, you get the language from the
`.pre-commit-hooks.yaml` of its GitHub or GitLab repository at `rev`; when that file is out of reach, you get a guess
from the shape of the dependency. You see changes on disk for files with a new version, with their line endings intact.

See the [documentation](https://bump-deps-index.readthedocs.io) for all options.

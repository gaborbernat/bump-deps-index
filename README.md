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
`--file` you get the files whose names start with `requirements` or `constraints` and end in `.txt` or `.in`; with
`--file` you can name any such file, such as `dev-requirements.txt`. You get a non-zero exit code when you have no file
to update.

Without `--index-url` you get the index from `PIP_INDEX_URL`, `UV_DEFAULT_INDEX` or `UV_INDEX_URL`, then the default
index of the nearest `uv.toml` or `[tool.uv]` table, then `index-url` from your pip configuration, then your user
`uv.toml`. With an `--index-url` or `-i` line in a requirements file, or in a file it includes with `-r`, you get
updates from that index. For a named uv index you send the credentials from `UV_INDEX_<NAME>_USERNAME` and
`UV_INDEX_<NAME>_PASSWORD`.

uv reads `[tool.uv.sources]` for the `pyproject.toml` of a project, with the sources of its workspace root, and for a
PEP 723 script from the script's own `[tool.uv]` table. You look up a package such a table pins to an index on that
index, and keep the spec of one from git, a path or a URL. pip installs the packages of the other Python files, so you
get the default index there.

Without `--npm-registry` you get `NPM_CONFIG_REGISTRY`, then `registry` from the `.npmrc` in the working directory, then
from your user `.npmrc`. From those files you get the `@scope:registry` of a scoped package and the `_authToken` or
`_auth` credentials of each registry.

Set `[project].requires-python` in a `pyproject.toml` and you get Python updates from distributions that support the
oldest interpreter you allow there, for files in that directory and its subdirectories. For a PEP 723 script with its
own `requires-python`, you get updates for that range. Without either field, you get the newest release on the index.

For a package you name on the command line, you get the `requires-python` floor and the `[tool.uv.sources]` index pins
of the project in the working directory. By default you accept pre-releases in `.pre-commit-config.yaml` and stable
releases in the other files; `-p yes` or `-p no` sets one rule for all of them.

For an `==` pin you get a newer release or no change, and you keep wildcards at their depth, so you go from `==1.*` to
`==2.*`. On `~=` bounds you keep the precision you wrote, so you go from `~=1.4` to `~=1.9`. You keep hashed
requirements as you wrote them, since you would need new hashes for a new version.

On npm ranges you stay inside the range, so `^1.2.0` goes to the newest `1.x` release and `~1.2.0` to the newest
`1.2.x`. You get the newest release for `>=1.2.0` and for a full or partial version, and you leave ranges such as
`1 || 2` or `latest` untouched. In `package.json` you get updates for `dependencies`, `devDependencies` and
`optionalDependencies`.

In `.pre-commit-config.yaml`, you get PyPI updates for `python` hooks and npm updates for `node` hooks, and no updates
for hooks in other languages. For a remote hook without a `language`, you get the language from the
`.pre-commit-hooks.yaml` of its GitHub or GitLab repository at `rev`; when that file is out of reach, you get a guess
from the shape of the dependency. You see changes on disk for files with a new version, with their line endings intact.

See the [documentation](https://bump-deps-index.readthedocs.io) for all options.

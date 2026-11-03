# bump-deps-index

[![PyPI](https://img.shields.io/pypi/v/bump-deps-index?style=flat-square)](https://pypi.org/project/bump-deps-index/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/bump-deps-index.svg)](https://pypi.org/project/bump-deps-index/)
[![check](https://github.com/gaborbernat/bump-deps-index/actions/workflows/check.yaml/badge.svg)](https://github.com/gaborbernat/bump-deps-index/actions/workflows/check.yaml)
[![Documentation Status](https://readthedocs.org/projects/bump-deps-index/badge/?version=latest)](https://bump-deps-index.readthedocs.io/en/latest/?badge=latest)
[![Downloads](https://static.pepy.tech/badge/bump-deps-index/month)](https://pepy.tech/project/bump-deps-index)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/gaborbernat/bump-deps-index/badge)](https://scorecard.dev/viewer/?uri=github.com/gaborbernat/bump-deps-index)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/16276/badge)](https://www.bestpractices.dev/projects/16276)

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

For the `pyproject.toml` of a project, with the settings of its workspace root, and for a PEP 723 script with its own
`[tool.uv]` table, you follow uv and take a package from the first index that has it: the indexes of `UV_INDEX` and
`UV_EXTRA_INDEX_URL`, then the `[[tool.uv.index]]` entries that are neither `default` nor `explicit`, then the default
index. For a package `[tool.uv.sources]` pins to an index, you query that index alone; for one from git, a path or a
URL, you keep the spec.

For the other Python files you follow pip and merge the releases of the default index with those of the extra indexes
from `PIP_EXTRA_INDEX_URL`, `extra-index-url` in your pip configuration and `--extra-index-url` lines.

Without `--npm-registry` you get `NPM_CONFIG_REGISTRY`, then `registry` from the `.npmrc` in the working directory, then
from your user `.npmrc`. From those files you get the `@scope:registry` of a scoped package and the `_authToken`,
`_auth` or `username` and `_password` credentials of each registry. As npm does, you get `${NAME}` from the environment,
and keep it as written when `NAME` is unset; you read `${NAME?}` as empty then.

Set `[project].requires-python` in a `pyproject.toml` and you get Python updates from distributions that support the
oldest interpreter you allow there, for files in that directory and its subdirectories. For a PEP 723 script with its
own `requires-python`, you get updates for that range. Without either field, you get the newest release on the index.

For a package you name on the command line, you get the `requires-python` floor and the `[tool.uv.sources]` index pins
of the project in the working directory. By default you accept pre-releases in `.pre-commit-config.yaml` and stable
releases in the other files; `-p yes` or `-p no` sets one rule for all of them.

For an `==` pin you move to the highest release the other specifiers allow, or leave the pin as written, and you keep
wildcards at their depth, so you go from `==1.*` to `==2.*`. You move a pin with a local label, such as `==1.0+cpu`,
only to a release with the same label. On `~=` bounds you keep the precision you wrote, so you go from `~=1.4` to
`~=1.9`. You keep hashed requirements as you wrote them, since you would need new hashes for a new version.

On npm ranges you stay inside the range, so `^1.2.0` goes to the newest `1.x` release and `~1.2.0` to the newest
`1.2.x`. You get the newest release for `>=1.2.0` and for a full or partial version, and you leave ranges such as
`1 || 2`, `latest` or an empty one untouched. As npm does, you get the `latest` dist-tag over a newer release when it
fits the range. In `package.json` you get updates for `dependencies`, `devDependencies` and `optionalDependencies`.

With `--exclude-newer` you only move to releases uploaded before the cutoff, and the flag beats every other source.
`--no-exclude-newer` drops the cutoff altogether, beating every other source as well, and the two flags cannot be
combined. Without a flag you get the cutoff from `PIP_UPLOADED_PRIOR_TO`, then `UV_EXCLUDE_NEWER` (the variable uv reads
for its lock step), then `exclude-newer` in the nearest `uv.toml` or `[tool.uv]` table, then `uploaded-prior-to` in your
pip configuration, then `exclude-newer` in your user `uv.toml`. The first one set wins. An `exclude-newer = false` in a
uv file disables the cutoff and stops the lookup, so the pip configuration and the user `uv.toml` are not read; an
environment variable still ranks above it.

The cutoff is an RFC 3339 timestamp, a local date, a datetime without an offset (read as local time), or a duration
counted back from now, such as `P7D` or `7 days`. As uv does, you skip a file without an upload time. You read upload
times from the PEP 700 fields of the JSON simple API and from the `time` map of the npm registry, so an index that
serves only HTML offers no candidates under a cutoff. A requirement already above the newest eligible release keeps its
floor.

In `.pre-commit-config.yaml`, you get PyPI updates for `python` hooks and npm updates for `node` hooks, and no updates
for hooks in other languages. For a remote hook without a `language`, you get the language from the
`.pre-commit-hooks.yaml` of its GitHub or GitLab repository at `rev`; when that file is out of reach, you get a guess
from the shape of the dependency. You see changes on disk for files with a new version, with their line endings intact.

See the [documentation](https://bump-deps-index.readthedocs.io) for all options.

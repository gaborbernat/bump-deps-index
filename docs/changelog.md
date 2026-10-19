# Changelog

<!-- towncrier release notes start -->

<a name="release-1-17-1"></a>

## 1.17.1 (2026-10-18)

<a name="release-1-17-1-documentation"></a>

### Documentation

- Document earlier releases and require changelog entries for pull requests
  ([#269](https://github.com/gaborbernat/bump-deps-index/pull/269)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-17-0"></a>

## 1.17.0 (2026-10-08)

<a name="release-1-17-0-added"></a>

### Added

- Update `package.json` `dependencies`, `devDependencies` and `optionalDependencies`
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Update `[tool.uv] dev-dependencies` in `pyproject.toml`
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Pass any `.txt` or `.in` file with `--file`, such as `dev-requirements.txt`, and find `constraints*` files on your own
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Read the default index from `UV_DEFAULT_INDEX`, `UV_INDEX_URL`, the nearest `uv.toml` or `[tool.uv]` table, your pip
  configuration and your user `uv.toml`, and the npm registry from `.npmrc`
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Follow uv for a project's `pyproject.toml` and for PEP 723 scripts: take a package from the first index that has it,
  starting with `UV_INDEX`, `UV_EXTRA_INDEX_URL` and the `[[tool.uv.index]]` entries that are neither `default` nor
  `explicit` ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by
  [@gaborbernat](https://github.com/gaborbernat).
- Look up a package that `[tool.uv.sources]` pins to an index on that index, and keep the spec of a package from git, a
  path or a URL ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by
  [@gaborbernat](https://github.com/gaborbernat).
- Follow pip for the other files: use the `--index-url` of a requirements file and the files it includes, and merge
  `PIP_EXTRA_INDEX_URL`, `extra-index-url` and `--extra-index-url` with the default index
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Send the `_authToken`, `_auth` or `username` and `_password` credential from `.npmrc`, matched the way npm walks the
  registry path, and route `@scope/*` packages to their `@scope:registry`
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Send uv index credentials from `UV_INDEX_<NAME>_USERNAME` and `UV_INDEX_<NAME>_PASSWORD`
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Read the language of a remote pre-commit hook from its `.pre-commit-hooks.yaml` on GitHub or GitLab
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-17-0-changes"></a>

### Changes

- Keep npm ranges inside their range: `^1.2.0` moves to the newest `1.x` release and `~1.2.0` to the newest `1.2.x`, and
  you take the `latest` dist-tag when it fits the range
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Keep wildcard pins at their depth, so `foo==1.*` gives `foo==2.*`
  ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264)) by [@gaborbernat](https://github.com/gaborbernat).
- Move an `==` pin to the highest release the other specifiers allow, and keep a local label such as `+cpu`
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Look up `python` pre-commit hooks on PyPI and `node` hooks on npm, and skip hooks in other languages
  ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264)) by [@gaborbernat](https://github.com/gaborbernat).
- Use a PEP 723 script's own `requires-python` in place of the project's
  ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264)) by [@gaborbernat](https://github.com/gaborbernat).
- Skip file discovery when you pass package names ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264)) by
  [@gaborbernat](https://github.com/gaborbernat).
- Print results in file order, and exit with a failure when you find no file to update
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-17-0-fixed"></a>

### Fixed

- Write the update for layouts you saw bumped in the output but not on disk: `additional_dependencies` as the first key
  of a hook, flow lists over several lines, spaced table headers such as `[ project ]`, dotted keys, `replace` tables in
  `tox.toml`, `{py311,py312}:` factors in `tox.ini` and requirements continued with `\`
  ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264))
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Stop rewriting text the loader did not read, such as multi-line strings, comments, skipped hooks and nested
  `package.json` objects ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264))
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Keep the extras, markers and spacing of a requirement when you add a lower bound
  ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264)) by [@gaborbernat](https://github.com/gaborbernat).
- Keep YAML anchors, tags and quoting in `.pre-commit-config.yaml`, and quote a value in a flow list once it gains a
  comma ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by
  [@gaborbernat](https://github.com/gaborbernat).
- Read `tox.ini` and `setup.cfg` as UTF-8, and drop inline comments in `setup.cfg` the way setuptools does
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Ignore files of other projects on an index page, such as `foo_bar` on the `foo` page
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).
- Report a malformed config file or registry answer as a failed lookup instead of a traceback
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-17-0-security"></a>

### Security

- Redact the password of a direct-reference URL and passwords that hold a quote from the output
  ([#264](https://github.com/gaborbernat/bump-deps-index/pull/264))
  ([#265](https://github.com/gaborbernat/bump-deps-index/pull/265)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.16.0...1.17.0

<a name="release-1-16-0"></a>

## 1.16.0 (2026-10-03)

<a name="release-1-16-0-changes"></a>

### Changes

- Edit the spec text you wrote, so your formatting stays and a spec at the newest version stays as is
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Resolve all files in one batch over one HTTP client, so a package you list in two files costs one request
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Request the PEP 691 JSON page from PyPI and abbreviated metadata from npm, which parse faster and transfer less
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-16-0-fixed"></a>

### Fixed

- Keep `foo==2.0b1` when you refuse pre-releases, instead of moving it down to `foo==1.9`
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Keep `===` pins as the full version string, so `foo===2.0.0` gives `foo===3.0.0`
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Write the bump for one-line `deps = X` values in `tox.ini` and `setup.cfg`; before, you saw it in the output with no
  change on disk ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by
  [@gaborbernat](https://github.com/gaborbernat).
- Leave hashed requirements and entries without a project name, such as `./local`, untouched
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Keep CRLF line endings and skip writing files that did not change
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Look up the `additional_dependencies` of `language: node` pre-commit hooks on npm
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Report a missing or unsupported `--file` in one line with exit code 1, and still update the other files
  ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by [@gaborbernat](https://github.com/gaborbernat).
- Read `requires-python` from the nearest `pyproject.toml` of each file, so a run from a parent folder uses the right
  floor ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by
  [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-16-0-security"></a>

### Security

- Strip credentials from URLs in error messages ([#261](https://github.com/gaborbernat/bump-deps-index/pull/261)) by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.15.0...1.16.0

<a name="release-1-15-0"></a>

## 1.15.0 (2026-10-02)

<a name="release-1-15-0-added"></a>

### Added

- Declare Python 3.15 support ([#242](https://github.com/gaborbernat/bump-deps-index/pull/242)) by
  [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-15-0-changes"></a>

### Changes

- Format Markdown and YAML with mdformat and yamlfmt in place of prettier
  ([#239](https://github.com/gaborbernat/bump-deps-index/pull/239)). No change to behavior by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.14.0...1.15.0

<a name="release-1-14-0"></a>

## 1.14.0 (2026-07-15)

<a name="release-1-14-0-added"></a>

### Added

- Read `requires-python` from `pyproject.toml` and skip releases that need a newer Python than your project allows
  ([#238](https://github.com/gaborbernat/bump-deps-index/pull/238)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-14-0-fixed"></a>

### Fixed

- Rewrite only dependency values, so comments, commands, URLs and hashes keep their text
  ([#238](https://github.com/gaborbernat/bump-deps-index/pull/238)) by [@gaborbernat](https://github.com/gaborbernat).
- Follow semver on npm and keep three-part pins ([#238](https://github.com/gaborbernat/bump-deps-index/pull/238)) by
  [@gaborbernat](https://github.com/gaborbernat).
- Exit with a failure when any lookup fails ([#238](https://github.com/gaborbernat/bump-deps-index/pull/238)) by
  [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-14-0-security"></a>

### Security

- Redact index credentials from the CLI output ([#238](https://github.com/gaborbernat/bump-deps-index/pull/238)) by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.13.0...1.14.0

<a name="release-1-13-0"></a>

## 1.13.0 (2026-06-13)

<a name="release-1-13-0-added"></a>

### Added

- Update dependencies inside `tox.toml` substitutions: both branches of `if`, and the `default` of `posargs`, `env` and
  `glob` ([#228](https://github.com/gaborbernat/bump-deps-index/pull/228)) by
  [@gaborbernat](https://github.com/gaborbernat).
- Update `deps` in `env_base` templates of `tox.toml` ([#228](https://github.com/gaborbernat/bump-deps-index/pull/228))
  by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-13-0-security"></a>

### Security

- Harden the GitHub workflows with zizmor and least-privilege permissions
  ([#200](https://github.com/gaborbernat/bump-deps-index/pull/200))
  ([#210](https://github.com/gaborbernat/bump-deps-index/pull/210)) by [@gaborbernat](https://github.com/gaborbernat).
- Add a security policy by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.12.0...1.13.0

<a name="release-1-12-0"></a>

## 1.12.0 (2026-01-21)

<a name="release-1-12-0-added"></a>

### Added

- Update the `dependencies` of PEP 723 inline script metadata in Python scripts
  ([#194](https://github.com/gaborbernat/bump-deps-index/pull/194)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-12-0-fixed"></a>

### Fixed

- Edit only the dependency sections of each file. Before, a version string anywhere in the file changed, and bumping
  `pytest` could touch `pytest-httpx` ([#194](https://github.com/gaborbernat/bump-deps-index/pull/194)) by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.11.0...1.12.0

<a name="release-1-11-0"></a>

## 1.11.0 (2026-01-14)

<a name="release-1-11-0-added"></a>

### Added

- Update `deps` in `tox.toml` environments, `env_run_base` and other sections
  ([#192](https://github.com/gaborbernat/bump-deps-index/pull/192)) by [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-11-0-fixed"></a>

### Fixed

- Skip pip options such as `-e .` and `-r other.txt` in `tox.ini` and requirements files instead of failing on them
  ([#192](https://github.com/gaborbernat/bump-deps-index/pull/192)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.10.0...1.11.0

<a name="release-1-10-0"></a>

## 1.10.0 (2025-10-09)

<a name="release-1-10-0-changes"></a>

### Changes

- Raise the minimum versions of PyYAML and truststore and drop leftover Python 3.9 tooling
  ([#172](https://github.com/gaborbernat/bump-deps-index/pull/172)). Python 3.11 stays the minimum by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.9.0...1.10.0

<a name="release-1-9-0"></a>

## 1.9.0 (2025-08-29)

<a name="release-1-9-0-added"></a>

### Added

- Find requirements files with a suffix, such as `requirements-test.txt`
  ([#168](https://github.com/gaborbernat/bump-deps-index/pull/168)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.8.1...1.9.0

<a name="release-1-8-1"></a>

## 1.8.1 (2025-07-31)

<a name="release-1-8-1-fixed"></a>

### Fixed

- Stop crashing on npm packages and on tox.ini substitutions such as `{[testenv:sync]deps}`
  ([#163](https://github.com/gaborbernat/bump-deps-index/pull/163)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.8.0...1.8.1

<a name="release-1-8-0"></a>

## 1.8.0 (2025-07-30)

<a name="release-1-8-0-changes"></a>

### Changes

- Skip requirements files that `pip-compile` generated ([#162](https://github.com/gaborbernat/bump-deps-index/pull/162))
  by [@gaborbernat](https://github.com/gaborbernat).
- Skip the project's own name in its dependencies, such as `demo[test]` inside `demo`
  ([#161](https://github.com/gaborbernat/bump-deps-index/pull/161)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.7.0...1.8.0

<a name="release-1-7-0"></a>

## 1.7.0 (2025-07-28)

<a name="release-1-7-0-added"></a>

### Added

- Update `requirements.in` files; when a `requirements.in` sits next to a `requirements.txt`, you update the `.in` file
  and leave the compiled `.txt` alone ([#160](https://github.com/gaborbernat/bump-deps-index/pull/160)) by
  [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-7-0-changes"></a>

### Changes

- Move each file format into its own loader ([#157](https://github.com/gaborbernat/bump-deps-index/pull/157)) by
  [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-7-0-fixed"></a>

### Fixed

- Skip yanked releases on Python indexes ([#159](https://github.com/gaborbernat/bump-deps-index/pull/159)) by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.6.0...1.7.0

<a name="release-1-6-0"></a>

## 1.6.0 (2025-01-21)

<a name="release-1-6-0-added"></a>

### Added

- Send requests through the proxy from your environment and verify certificates against the system trust store, so the
  tool works behind corporate proxies ([#140](https://github.com/gaborbernat/bump-deps-index/pull/140)) by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.5.0...1.6.0

<a name="release-1-5-0"></a>

## 1.5.0 (2024-11-08)

<a name="release-1-5-0-added"></a>

### Added

- Update PEP 735 `[dependency-groups]` in `pyproject.toml` and `requires` in `tox.toml`
  ([#128](https://github.com/gaborbernat/bump-deps-index/pull/128)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.8...1.5.0

<a name="release-1-4-8"></a>

## 1.4.8 (2024-09-18)

<a name="release-1-4-8-changes"></a>

### Changes

- Fix the downloads badge in the README. No change to behavior by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.7...1.4.8

<a name="release-1-4-7"></a>

## 1.4.7 (2024-09-18)

<a name="release-1-4-7-changes"></a>

### Changes

- Rework the CI and rename the `test` extra to `testing`. No change to behavior by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.6...1.4.7

<a name="release-1-4-6"></a>

## 1.4.6 (2024-09-09)

<a name="release-1-4-6-fixed"></a>

### Fixed

- Keep single quotes in environment markers, so `A; python_version<'3.11'` keeps its quoting when you bump it
  ([#113](https://github.com/gaborbernat/bump-deps-index/pull/113)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.5...1.4.6

<a name="release-1-4-5"></a>

## 1.4.5 (2024-09-08)

<a name="release-1-4-5-added"></a>

### Added

- Support Python 3.13 by [@gaborbernat](https://github.com/gaborbernat).

- End Python 3.10 support; new releases require Python 3.11 or later by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.4...1.4.5

<a name="release-1-4-4"></a>

## 1.4.4 (2024-03-15)

<a name="release-1-4-4-fixed"></a>

### Fixed

- Skip versions on the npm registry that do not parse instead of failing the lookup
  ([#92](https://github.com/gaborbernat/bump-deps-index/pull/92)) by [@gaborbernat](https://github.com/gaborbernat).
- Read the name of a scoped npm package such as `@scope/name` with no version by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.3...1.4.4

<a name="release-1-4-3"></a>

## 1.4.3 (2023-06-16)

<a name="release-1-4-3-changes"></a>

### Changes

- Lint with ruff and test against the Python 3.12 beta ([#52](https://github.com/gaborbernat/bump-deps-index/pull/52))
  ([#53](https://github.com/gaborbernat/bump-deps-index/pull/53)). No change to behavior by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.2...1.4.3

<a name="release-1-4-2"></a>

## 1.4.2 (2023-05-03)

<a name="release-1-4-2-fixed"></a>

### Fixed

- Parse index pages as HTML again; 1.4.1 read them as XML and failed on pages that are not valid XML
  ([#49](https://github.com/gaborbernat/bump-deps-index/pull/49)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.1...1.4.2

<a name="release-1-4-1"></a>

## 1.4.1 (2023-04-28)

<a name="release-1-4-1-added"></a>

### Added

- Support Python 3.12 ([#46](https://github.com/gaborbernat/bump-deps-index/pull/46)) by
  [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-4-1-changes"></a>

### Changes

- Publish to PyPI through trusted publishing ([#45](https://github.com/gaborbernat/bump-deps-index/pull/45)) by
  [@gaborbernat](https://github.com/gaborbernat).

<a name="release-1-4-1-removed"></a>

### Removed

- The `lxml` dependency; the standard library parses index pages
  ([#46](https://github.com/gaborbernat/bump-deps-index/pull/46)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.4.0...1.4.1

<a name="release-1-4-0"></a>

## 1.4.0 (2022-11-28)

<a name="release-1-4-0-added"></a>

### Added

- Update `requirements.txt` files by [@gaborbernat](https://github.com/gaborbernat).
- Choose pre-release handling with `--pre-release yes|no|file-default`. The default accepts pre-releases in
  `.pre-commit-config.yaml` and refuses them elsewhere by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.3.0...1.4.0

<a name="release-1-3-0"></a>

## 1.3.0 (2022-08-21)

<a name="release-1-3-0-changes"></a>

### Changes

- Skip pre-releases when you pick the newest version ([#5](https://github.com/gaborbernat/bump-deps-index/pull/5)) by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.2.0...1.3.0

<a name="release-1-2-0"></a>

## 1.2.0 (2022-08-13)

<a name="release-1-2-0-added"></a>

### Added

- Update JavaScript dependencies pinned as `name@version` in pre-commit `additional_dependencies`
  ([#4](https://github.com/gaborbernat/bump-deps-index/pull/4)) by [@gaborbernat](https://github.com/gaborbernat).
- Pick the npm registry with `--npm-registry` or `NPM_CONFIG_REGISTRY` by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.1.0...1.2.0

<a name="release-1-1-0"></a>

## 1.1.0 (2022-08-03)

<a name="release-1-1-0-added"></a>

### Added

- Run without `--file` to update every supported file in the working directory, and pass `--file` more than once to name
  several ([#2](https://github.com/gaborbernat/bump-deps-index/pull/2)) by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.0.3...1.1.0

<a name="release-1-0-3"></a>

## 1.0.3 (2022-08-03)

<a name="release-1-0-3-fixed"></a>

### Fixed

- Drop the build label after `+` from the version you write, so a release such as `1.0+local` gives `>=1.0` by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.0.2...1.0.3

<a name="release-1-0-2"></a>

## 1.0.2 (2022-08-03)

<a name="release-1-0-2-fixed"></a>

### Fixed

- Read a `setup.cfg` without `[options]` or `[options.extras_require]` instead of failing on it
  ([#1](https://github.com/gaborbernat/bump-deps-index/pull/1)) by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.0.1...1.0.2

<a name="release-1-0-1"></a>

## 1.0.1 (2022-08-03)

<a name="release-1-0-1-fixed"></a>

### Fixed

- Parse index pages with `lxml`, so an index that serves HTML instead of well-formed XML no longer fails the lookup by
  [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/compare/1.0.0...1.0.1

<a name="release-1-0-0"></a>

## 1.0.0 (2022-08-03)

<a name="release-1-0-0-added"></a>

### Added

- First release. Pass package names to see their newest versions on PyPI, or pass `--file` to raise the lower bounds in
  `pyproject.toml`, `tox.ini`, `setup.cfg` or `.pre-commit-config.yaml` in place by
  [@gaborbernat](https://github.com/gaborbernat).
- Pick the index with `--index-url` or `PIP_INDEX_URL` by [@gaborbernat](https://github.com/gaborbernat).

**Full Changelog**: https://github.com/gaborbernat/bump-deps-index/commits/1.0.0

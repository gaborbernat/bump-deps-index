# Contributing

Add a changelog fragment under `docs/changelog.d` for a pull request that changes what people can use or observe. Name
it `+short-name.<type>.md`, for example `+support-uv-index.feature.md`. The `+short-name` part is descriptive; you do
not need a pull request number before opening the pull request. Write one change per fragment. A pull request with
several user-visible changes can include several fragments.

Choose the type by the effect on users:

| Type          | Changelog section | Use for                                                          |
| ------------- | ----------------- | ---------------------------------------------------------------- |
| `feature`     | Added             | A new capability, including Python support additions or removals |
| `change`      | Changes           | A changed behavior that remains available                        |
| `bugfix`      | Fixed             | A corrected behavior                                             |
| `doc`         | Documentation     | A documentation change users need to know about                  |
| `breaking`    | Breaking changes  | A behavior that requires users to change their usage             |
| `security`    | Security          | A security fix users need to act on                              |
| `performance` | Performance       | A user-visible speed or resource improvement                     |
| `deprecation` | Deprecated        | A supported behavior scheduled for removal                       |
| `removal`     | Removed           | A removed user-facing capability                                 |
| `packaging`   | Packaging         | An install, wheel, or distribution change                        |

Use the `skip news` label for a pull request that has no user-visible change. The label can be added after the pull
request opens. A supplied fragment is still checked when the label is present; empty fragments and unknown types fail.
Bot pull requests need no fragment unless they include one. Do not write a fragment for internal maintenance alone.

The release workflow adds the merged pull request link and checks the pull request author. If several people authored
the change, add their linked GitHub handles in the fragment with `by`; omit bots. The tracked changelog uses those
links, while GitHub Release notes use `@handle` mentions.

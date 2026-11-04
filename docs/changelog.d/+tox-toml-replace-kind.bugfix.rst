Skip a ``replace`` substitution in ``tox.toml`` whose kind is a list or a table instead of a string, so it no longer
ends the run with a traceback; the other dependencies in the file still update.

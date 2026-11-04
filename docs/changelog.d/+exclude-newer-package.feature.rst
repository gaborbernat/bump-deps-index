Added ``--exclude-newer-package NAME=CUTOFF``, repeatable, to give one package its own cutoff in place of
``--exclude-newer``, and ``NAME=false`` to lift the cutoff for that package. The ``exclude-newer-package`` table in
project and user ``uv`` settings sets the same per-package cutoffs.

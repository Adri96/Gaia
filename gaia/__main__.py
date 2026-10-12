"""``python -m gaia <case> [args]`` — same as the ``gaia`` command."""

import sys

from gaia.cli import main

sys.exit(main())

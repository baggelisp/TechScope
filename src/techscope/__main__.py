"""Allows ``python -m techscope`` alongside the installed ``techscope`` console script."""

import sys

from techscope.presentation.cli import main

if __name__ == "__main__":
    sys.exit(main())

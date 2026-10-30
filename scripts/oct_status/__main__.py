"""Run the status system: ``python -m oct_status``."""

import sys

from oct_status.main import cli

if __name__ == "__main__":
    sys.exit(cli())

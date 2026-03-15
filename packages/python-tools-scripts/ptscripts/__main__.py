from __future__ import annotations

import logging
from typing import NoReturn

from ptscripts.parser import Parser

logger = logging.getLogger(__name__)


def main() -> NoReturn:  # type: ignore[misc]
    """
    Main CLI entry-point for python tools scripts.
    """
    parser = Parser()
    logger.debug("Searching for tools in %s...")
    parser.parse_args()


if __name__ == "__main__":
    main()

from __future__ import annotations

import logging
import os
import pathlib
import sys
from typing import NoReturn

from ptscripts.parser import Parser

CWD: pathlib.Path = pathlib.Path.cwd()
if "TOOLS_SCRIPTS_PATH" in os.environ:
    _BASE_PATH = pathlib.Path(os.environ["TOOLS_SCRIPTS_PATH"]).expanduser()
else:
    _BASE_PATH = CWD
TOOLS_VENVS_PATH = _BASE_PATH / ".tools-venvs" / "py{}.{}".format(*sys.version_info)

DEFAULT_TOOLS_VENV_PATH = TOOLS_VENVS_PATH / "default"
if str(DEFAULT_TOOLS_VENV_PATH) in sys.path:
    sys.path.remove(str(DEFAULT_TOOLS_VENV_PATH))

log = logging.getLogger(__name__)


def main() -> NoReturn:  # type: ignore[misc]
    """
    Main CLI entry-point for python tools scripts.
    """
    parser = Parser()
    cwd = str(parser.repo_root)
    log.debug("Searching for tools in %s", cwd)
    if cwd in sys.path:
        sys.path.remove(cwd)
    sys.path.insert(0, cwd)
    try:
        import tools  # noqa: F401
    except ImportError as exc:
        if os.environ.get("TOOLS_DEBUG_IMPORTS", "0") == "1":
            raise exc from None

    parser.parse_args()


if __name__ == "__main__":
    main()

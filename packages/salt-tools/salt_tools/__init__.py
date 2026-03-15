import logging
import pathlib
import sys

import ptscripts

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Don't set up any default config - trust that the current venv is set up correctly
# with dev dependencies already installed (pydantic, rich, etc.)

ptscripts.register_tools_module("tools.changelog")
ptscripts.register_tools_module("tools.ci")
ptscripts.register_tools_module("tools.container")
ptscripts.register_tools_module("tools.docs")
ptscripts.register_tools_module("tools.gh")
ptscripts.register_tools_module("tools.pkg")
ptscripts.register_tools_module("tools.pkg.build")
ptscripts.register_tools_module("tools.precommit")
ptscripts.register_tools_module("tools.precommit.changelog")
ptscripts.register_tools_module("tools.precommit.workflows")
ptscripts.register_tools_module("tools.precommit.docs")
ptscripts.register_tools_module("tools.precommit.docstrings")
ptscripts.register_tools_module("tools.precommit.filemap")
ptscripts.register_tools_module("tools.precommit.loader")
ptscripts.register_tools_module("tools.release")
ptscripts.register_tools_module("tools.testsuite")
ptscripts.register_tools_module("tools.testsuite.download")

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)

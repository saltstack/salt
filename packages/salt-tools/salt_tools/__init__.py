import logging
import pathlib
import sys

import ptscripts

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Don't set up any default config - trust that the current venv is set up correctly
# with dev dependencies already installed (pydantic, rich, etc.)

ptscripts.register_tools_module("salt_tools.changelog")
ptscripts.register_tools_module("salt_tools.ci")
ptscripts.register_tools_module("salt_tools.container")
ptscripts.register_tools_module("salt_tools.docs")
ptscripts.register_tools_module("salt_tools.gh")
ptscripts.register_tools_module("salt_tools.pkg")
ptscripts.register_tools_module("salt_tools.pkg.build")
ptscripts.register_tools_module("salt_tools.precommit")
ptscripts.register_tools_module("salt_tools.precommit.changelog")
ptscripts.register_tools_module("salt_tools.precommit.workflows")
ptscripts.register_tools_module("salt_tools.precommit.docs")
ptscripts.register_tools_module("salt_tools.precommit.docstrings")
ptscripts.register_tools_module("salt_tools.precommit.filemap")
ptscripts.register_tools_module("salt_tools.precommit.loader")
ptscripts.register_tools_module("salt_tools.release")
ptscripts.register_tools_module("salt_tools.testsuite")
ptscripts.register_tools_module("salt_tools.testsuite.download")

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)

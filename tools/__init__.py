import logging
import pathlib
import sys

import ptscripts
from ptscripts.parser import DefaultRequirementsConfig
from ptscripts.virtualenv import VirtualEnvConfig

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIREMENTS_FILES_PATH = REPO_ROOT / "requirements"
STATIC_REQUIREMENTS_PATH = REQUIREMENTS_FILES_PATH / "static"
CI_REQUIREMENTS_FILES_PATH = (
    STATIC_REQUIREMENTS_PATH / "ci" / "py{}.{}".format(*sys.version_info)
)
PKG_REQUIREMENTS_FILES_PATH = (
    STATIC_REQUIREMENTS_PATH / "pkg" / "py{}.{}".format(*sys.version_info)
)
DEFAULT_REQS_CONFIG = DefaultRequirementsConfig(
    pip_args=[
        f"--constraint={REQUIREMENTS_FILES_PATH / 'constraints.txt'}",
        f"--constraint={PKG_REQUIREMENTS_FILES_PATH / 'linux.txt'}",
    ],
    requirements_files=[
        REQUIREMENTS_FILES_PATH / "base.txt",
        CI_REQUIREMENTS_FILES_PATH / "tools.txt",
    ],
)
RELEASE_VENV_CONFIG = VirtualEnvConfig(
    env={
        "PIP_CONSTRAINT": str(REQUIREMENTS_FILES_PATH / "constraints.txt"),
    },
    pip_args=[
        f"--constraint={REQUIREMENTS_FILES_PATH / 'constraints.txt'}",
        f"--constraint={PKG_REQUIREMENTS_FILES_PATH / 'linux.txt'}",
    ],
    requirements_files=[
        CI_REQUIREMENTS_FILES_PATH / "tools-virustotal.txt",
    ],
    add_as_extra_site_packages=True,
)
ptscripts.set_default_requirements_config(DEFAULT_REQS_CONFIG)
ptscripts.register_tools_module("tools.changelog")
ptscripts.register_tools_module("tools.ci")
ptscripts.register_tools_module("tools.docs")
ptscripts.register_tools_module("tools.pkg")
ptscripts.register_tools_module("tools.pkg.repo")
ptscripts.register_tools_module("tools.pkg.build")
ptscripts.register_tools_module("tools.pkg.repo.create")
ptscripts.register_tools_module("tools.pkg.repo.publish")
ptscripts.register_tools_module("tools.precommit")
ptscripts.register_tools_module("tools.precommit.changelog")
ptscripts.register_tools_module("tools.precommit.workflows")
ptscripts.register_tools_module("tools.precommit.docs")
ptscripts.register_tools_module("tools.precommit.docstrings")
ptscripts.register_tools_module("tools.precommit.filemap")
ptscripts.register_tools_module("tools.precommit.loader")
ptscripts.register_tools_module("tools.release", venv_config=RELEASE_VENV_CONFIG)
ptscripts.register_tools_module("tools.testsuite")
ptscripts.register_tools_module("tools.testsuite.download")
ptscripts.register_tools_module("tools.vm")

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)

import json
import logging
import pathlib
import sys
import textwrap
from subprocess import CompletedProcess

import ptscripts
import ptscripts.virtualenv
from ptscripts.models import DefaultPipConfig, VirtualEnvPipConfig


def _add_as_extra_site_packages(self) -> None:
    if self.config.add_as_extra_site_packages is False:
        return
    ret = self.run_code(
        "import json,site; print(json.dumps(site.getsitepackages()))",
        capture=True,
        check=False,
    )
    if ret.returncode:
        self.ctx.error(
            f"1 Failed to get the virtualenv's site packages path: {ret.returncode} {ret.stdout.decode()}  {ret.stderr.decode()}"
        )
        self.ctx.exit(1)
    for path in json.loads(ret.stdout.strip().decode()):
        if path not in sys.path:
            sys.path.append(path)


def _remove_extra_site_packages(self) -> None:
    if self.config.add_as_extra_site_packages is False:
        return
    ret = self.run_code(
        "import json,site; print(json.dumps(site.getsitepackages()))",
        capture=True,
        check=False,
    )
    if ret.returncode:
        self.ctx.error(
            f"2 Failed to get the virtualenv's site packages path: {ret.stdout.decode()} {ret.stderr.decode()}"
        )
        self.ctx.exit(1)
    for path in json.loads(ret.stdout.strip().decode()):
        if path in sys.path:
            sys.path.remove(path)


def run_code(
    self, code_string: str, python: str | None = None, **kwargs
) -> CompletedProcess[bytes]:
    """
    Run a code string against the virtual environment.
    """
    if code_string.startswith("\n"):
        code_string = code_string[1:]
    code_string = textwrap.dedent(code_string).rstrip()
    # log.debug("Code to run passed to python:\n>>>>>>>>>>\n%s\n<<<<<<<<<<", code_string)
    self.ctx.info(f"Python iterpreter {self.venv_python}")
    if python is None:
        python = str(self.venv_python)
    return self.run(python, "-c", code_string, **kwargs)


ptscripts.virtualenv.VirtualEnv._add_as_extra_site_packages = (
    _add_as_extra_site_packages
)
ptscripts.virtualenv.VirtualEnv._remove_extra_site_packages = (
    _remove_extra_site_packages
)
ptscripts.virtualenv.VirtualEnv.run_code = run_code

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIREMENTS_FILES_PATH = REPO_ROOT / "requirements"
STATIC_REQUIREMENTS_PATH = REQUIREMENTS_FILES_PATH / "static"
CI_REQUIREMENTS_FILES_PATH = (
    STATIC_REQUIREMENTS_PATH / "ci" / "py{}.{}".format(*sys.version_info)
)
DEFAULT_REQS_CONFIG = DefaultPipConfig(
    install_args=[
        f"--constraint={REQUIREMENTS_FILES_PATH / 'constraints.txt'}",
    ],
    requirements_files=[
        CI_REQUIREMENTS_FILES_PATH / "tools.txt",
    ],
)
RELEASE_VENV_CONFIG = VirtualEnvPipConfig(
    install_args=[
        f"--constraint={REQUIREMENTS_FILES_PATH / 'constraints.txt'}",
    ],
    requirements_files=[
        CI_REQUIREMENTS_FILES_PATH / "tools-virustotal.txt",
    ],
    add_as_extra_site_packages=True,
)
ptscripts.set_default_config(DEFAULT_REQS_CONFIG)
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
ptscripts.register_tools_module("tools.release", venv_config=RELEASE_VENV_CONFIG)
ptscripts.register_tools_module("tools.testsuite")
ptscripts.register_tools_module("tools.testsuite.download")
ptscripts.register_tools_module("tools.vm")

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)

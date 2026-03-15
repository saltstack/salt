from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import textwrap
from subprocess import CompletedProcess
from typing import TYPE_CHECKING

import attr

if TYPE_CHECKING:
    import pathlib

    from ptscripts.models import VirtualEnvConfig
    from ptscripts.parser import Context

log = logging.getLogger(__name__)


@attr.s(frozen=True, slots=True)
class VirtualEnv:
    """
    Helper class to create and user virtual environments.
    """

    ctx: Context = attr.ib()
    config: VirtualEnvConfig = attr.ib()
    environ: dict[str, str] = attr.ib(init=False, repr=False)
    venv_dir: pathlib.Path = attr.ib(init=False)
    venv_python: pathlib.Path = attr.ib(init=False, repr=False)
    venv_bin_dir: pathlib.Path = attr.ib(init=False, repr=False)
    requirements_hash: str = attr.ib(init=False, repr=False)

    @venv_dir.default
    def _default_venv_dir(self) -> pathlib.Path:
        # Late import to avoid circular import errors
        from ptscripts.__main__ import TOOLS_VENVS_PATH

        venvs_path = TOOLS_VENVS_PATH
        venvs_path.mkdir(parents=True, exist_ok=True)
        return venvs_path / self.config.name

    @environ.default
    def _default_environ(self) -> dict[str, str]:
        environ = os.environ.copy()
        if self.config.env:
            environ.update(self.config.env)
        return environ

    @venv_python.default
    def _default_venv_python(self) -> pathlib.Path:
        if sys.platform.startswith("win"):
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    @venv_bin_dir.default
    def _default_venv_bin_dir(self) -> pathlib.Path:
        return self.venv_python.parent

    @requirements_hash.default
    def __default_requirements_hash(self) -> str:
        return self.config.get_config_hash()

    def _install_requirements(self) -> None:
        requirements_hash_file = self.venv_dir / ".requirements.hash"
        if (
            requirements_hash_file.exists()
            and requirements_hash_file.read_text() == self.requirements_hash
        ):
            # Requirements are up to date
            self.ctx.debug(
                f"Requirements for virtualenv({self.config.name}) haven't changed."
            )
            return
        self.config.install(self.ctx, python_executable=str(self.venv_python))
        self.venv_dir.joinpath(".requirements.hash").write_text(self.requirements_hash)

    def _create_virtualenv(self) -> None:
        # Late import to avoid circular import errors
        from ptscripts.__main__ import CWD

        if self.venv_dir.exists():
            if not self.venv_python.exists():
                try:
                    relative_venv_path = self.venv_dir.relative_to(CWD)
                except ValueError:
                    relative_venv_path = self.venv_dir
                try:
                    relative_venv_python_path = self.venv_python.relative_to(CWD)
                except ValueError:
                    relative_venv_python_path = self.venv_python
                self.ctx.warn(
                    f"The virtual environment path '{relative_venv_path}' exists but the "
                    f"python binary '{relative_venv_python_path}' does not. Deleting the "
                    "virtual environment."
                )
                shutil.rmtree(self.venv_dir)
            else:
                self.ctx.debug("Virtual environment path already exists")
                return
        virtualenv = shutil.which("virtualenv")
        if virtualenv:
            cmd = [
                virtualenv,
                f"--python={self.get_real_python()}",
            ]
        else:
            cmd = [
                self.get_real_python(),
                "-m",
                "venv",
            ]
        if self.config.system_site_packages:
            cmd.append("--system-site-packages")
        cmd.append(str(self.venv_dir))
        try:
            relative_venv_path = self.venv_dir.relative_to(CWD)
        except ValueError:
            relative_venv_path = self.venv_dir
        self.ctx.info(
            f"Creating virtualenv({self.config.name}) in {relative_venv_path}"
        )
        self.run(*cmd, cwd=str(self.venv_dir.parent))
        self.install(
            "-U",
            "wheel",
            self.config.pip_requirement,
            self.config.setuptools_requirement,
        )

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
                f"Failed to get the virtualenv's site packages path: {ret.stderr.decode()}"
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
                f"Failed to get the virtualenv's site packages path: {ret.stderr.decode()}"
            )
            self.ctx.exit(1)
        for path in json.loads(ret.stdout.strip().decode()):
            if path in sys.path:
                sys.path.remove(path)

    def __enter__(self) -> VirtualEnv:
        """
        Creates the virtual environment when entering context.
        """
        try:
            self._create_virtualenv()
        except subprocess.CalledProcessError:
            msg = "Failed to create virtualenv"
            raise AssertionError(msg) from None
        try:
            self._install_requirements()
        except FileNotFoundError:
            # attempt to fix the virtualenv. delete and start over
            shutil.rmtree(str(self.venv_dir))
            try:
                self._create_virtualenv()
            except subprocess.CalledProcessError:
                msg = "Failed to create virtualenv"
                raise AssertionError(msg) from None
            self._install_requirements()
        self._add_as_extra_site_packages()
        return self

    def __exit__(self, *args) -> None:
        """
        Exit the virtual environment context.
        """
        self._remove_extra_site_packages()

    def install(self, *args: str, **kwargs) -> CompletedProcess[bytes]:
        """
        Install the passed python packages.
        """
        return self.run(str(self.venv_python), "-m", "pip", "install", *args, **kwargs)

    def uninstall(self, *args, **kwargs) -> CompletedProcess[bytes]:
        """
        Uninstall the passed python packages.
        """
        return self.run(
            str(self.venv_python), "-m", "pip", "uninstall", "-y", *args, **kwargs
        )

    def run(self, *args: str, **kwargs) -> CompletedProcess[bytes]:
        """
        Run a command in the context of the virtual environment.
        """
        # Late import to avoid circular import errors
        from ptscripts.__main__ import CWD

        kwargs.setdefault("cwd", CWD)
        env = kwargs.pop("env", None)
        environ = self.environ.copy()
        if env:
            environ.update(env)
        if "PATH" not in environ:
            environ["PATH"] = str(self.venv_bin_dir)
        else:
            environ["PATH"] = f"{self.venv_bin_dir}{os.pathsep}{environ['PATH']}"
        return self.ctx._run(*args, env=environ, **kwargs)  # noqa: SLF001

    @staticmethod
    def get_real_python() -> str:
        """
        Get the real python binary.

        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, on windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        """
        try:
            if sys.platform.startswith("win"):
                return os.path.join(sys.real_prefix, os.path.basename(sys.executable))
            python_binary_names = [
                "python{}.{}".format(*sys.version_info),
                "python{}".format(*sys.version_info),
                "python",
            ]
            for binary_name in python_binary_names:
                python = os.path.join(sys.real_prefix, "bin", binary_name)  # type: ignore[attr-defined]
                if os.path.exists(python):
                    return python
            msg = "Couldn't find a python binary name under '{}' matching: {}".format(
                os.path.join(sys.real_prefix, "bin"), python_binary_names  # type: ignore[attr-defined]
            )
            raise AssertionError(msg)  # noqa: TRY301
        except AttributeError:
            return sys.executable

    def run_code(
        self, code_string: str, python: str | None = None, **kwargs
    ) -> CompletedProcess[bytes]:
        """
        Run a code string against the virtual environment.
        """
        if code_string.startswith("\n"):
            code_string = code_string[1:]
        code_string = textwrap.dedent(code_string).rstrip()
        log.debug(
            "Code to run passed to python:\n>>>>>>>>>>\n%s\n<<<<<<<<<<", code_string
        )
        if python is None:
            python = str(self.venv_python)
        return self.run(python, "-c", code_string, **kwargs)

    def get_installed_packages(self) -> dict[str, str]:
        """
        Get the installed packages in the virtual environment.
        """
        data = {}
        ret = self.run(str(self.venv_python), "-m", "pip", "list", "--format", "json")
        for pkginfo in json.loads(ret.stdout):
            data[pkginfo["name"]] = pkginfo["version"]
        return data

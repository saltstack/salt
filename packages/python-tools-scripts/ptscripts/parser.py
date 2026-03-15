"""
Python tools scripts CLI parser.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import logging
import os
import pathlib
import subprocess
import sys
import typing
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager, nullcontext
from functools import partial
from subprocess import CompletedProcess
from types import FunctionType, GenericAlias
from typing import TYPE_CHECKING, Any, Concatenate, NoReturn, ParamSpec, TypeVar, cast

import requests
import rich
from ptscripts import logs, process
from ptscripts.models import VirtualEnvConfig, VirtualEnvPipConfig
from ptscripts.virtualenv import VirtualEnv
from rich.console import Console
from rich.theme import Theme

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired, TypedDict
else:
    from typing import NotRequired, TypedDict

try:
    import importlib.metadata

    __version__ = importlib.metadata.version("python-tools-scripts")
except ImportError:
    import importlib_metadata

    try:
        __version__ = importlib_metadata.version("python-tools-scripts")
    except Exception:
        __version__ = "unknown"
except Exception:
    __version__ = "unknown"

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace, _SubParsersAction
    from collections.abc import Iterator

    from ptscripts.models import DefaultConfig


Param = ParamSpec("Param")
RetType = TypeVar("RetType")
OriginalFunc = Callable[Param, RetType]
DecoratedFunc = Callable[Concatenate[str, Param], RetType]

log = logging.getLogger(__name__)


class ArgumentOptions(TypedDict):
    """
    TypedDict class documenting the acceptable keys and their types for arguments.
    """

    help: NotRequired[str]
    flags: NotRequired[list[str]]
    action: NotRequired[str | argparse.Action]
    nargs: NotRequired[int | str]
    const: NotRequired[Any]
    choices: NotRequired[list[str] | tuple[str, ...]]
    required: NotRequired[bool]
    metavar: NotRequired[str]
    default: NotRequired[Any]


class FullArgumentOptions(ArgumentOptions):
    """
    TypedDict class documenting the argparse.add_argument names and types.
    """

    dest: str
    type: type[Any]


class Context:
    """
    Context class passed to every command group function as the first argument.
    """

    def __init__(
        self, parser: Parser, debug: bool = False, quiet: bool = False
    ) -> None:
        self.parser = parser
        self._quiet = quiet
        self._debug = debug
        self.repo_root = parser.repo_root
        theme = Theme(
            {
                "log-debug": "dim blue",
                "log-info": "dim cyan",
                "log-warning": "magenta",
                "log-error": "bold red",
                "exit-ok": "green",
                "exit-failure": "bold red",
                "logging.level.stdout": "dim blue",
                "logging.level.stderr": "dim red",
            }
        )
        console_kwargs = {
            "theme": theme,
        }
        if os.environ.get("CI"):
            console_kwargs["force_terminal"] = True
            console_kwargs["force_interactive"] = False
        self.console = Console(stderr=True, log_path=False, **console_kwargs)
        self.console_stdout = Console(log_path=False, **console_kwargs)
        rich.reconfigure(stderr=True, **console_kwargs)
        self.venv = None

    def print(self, *args, **kwargs) -> None:
        """
        Print to stdout.
        """
        self.console_stdout.print(*args, **kwargs)

    def debug(self, *args) -> None:
        """
        Print debug message to stderr.
        """
        if self._debug:
            self.console.log(*args, style="log-debug", _stack_offset=2)

    def info(self, *args) -> None:
        """
        Print info message to stderr.
        """
        if not self._quiet:
            self.console.log(*args, style="log-info", _stack_offset=2)

    def warn(self, *args) -> None:
        """
        Print warning message to stderr.
        """
        self.console.log(*args, style="log-warning", _stack_offset=2)

    def error(self, *args) -> None:
        """
        Print error message to stderr.
        """
        self.console.log(*args, style="log-error", _stack_offset=2)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:  # type: ignore[misc]
        """
        Exit the command execution.
        """
        if message is not None:
            if status == 0:
                style = "exit-ok"
            else:
                style = "exit-failure"
            self.console.print(message, style=style)
        self.parser.exit(status)

    def _run(
        self,
        *cmdline: str,
        check: bool = True,
        timeout_secs: int | None = None,
        no_output_timeout_secs: int | None = None,
        capture: bool = False,
        interactive: bool = False,
        **kwargs,
    ) -> CompletedProcess[bytes]:
        """
        Run a subprocess.
        """
        return process.run(
            *cmdline,
            check=check,
            timeout_secs=timeout_secs,
            no_output_timeout_secs=no_output_timeout_secs,
            capture=capture,
            interactive=interactive,
            **kwargs,
        )

    def run(
        self,
        *cmdline: str,
        check: bool = True,
        timeout_secs: int | None = None,
        no_output_timeout_secs: int | None = None,
        capture: bool = False,
        interactive: bool = False,
        **kwargs,
    ) -> CompletedProcess[bytes]:
        """
        Run a subprocess.

        Either in a virtualenv context if one was configured or the system context.
        """
        self.debug(f"""Running '{" ".join(cmdline)}'""")
        try:
            if self.venv:
                return self.venv.run(
                    *cmdline,
                    check=check,
                    timeout_secs=timeout_secs,
                    no_output_timeout_secs=no_output_timeout_secs,
                    capture=capture,
                    interactive=interactive,
                    **kwargs,
                )
            return self._run(
                *cmdline,
                check=check,
                timeout_secs=timeout_secs,
                no_output_timeout_secs=no_output_timeout_secs,
                capture=capture,
                interactive=interactive,
                **kwargs,
            )
        except subprocess.CalledProcessError as exc:
            self._exit(str(exc), exc.returncode)

    def _exit(self, msg: str, returncode: int) -> NoReturn:
        self.error(msg)
        self.exit(returncode)

    @contextmanager
    def chdir(self, path: pathlib.Path) -> Iterator[pathlib.Path]:
        """
        Change the current working directory to the provided path.
        """
        cwd = pathlib.Path.cwd()
        try:
            os.chdir(path)
            yield path
        finally:
            if not cwd.exists():
                self.error(f"Unable to change back to path {cwd}")
            else:
                os.chdir(cwd)

    @contextmanager
    def virtualenv(
        self, name: str, config: VirtualEnvConfig | None = None
    ) -> Iterator[VirtualEnv]:
        """
        Create and use a virtual environment.
        """
        if config is None:
            config = VirtualEnvPipConfig(name=name)
        if config.name is None:
            config.name = name
        with VirtualEnv(ctx=self, config=config) as venv:
            yield venv

    @property
    def web(self) -> requests.Session:
        """
        Returns an instance of :py:class:`~requests.Session`.
        """
        return requests.Session()


class DefaultVirtualEnv:
    """
    Simple class to hold registered imports.
    """

    _instance: DefaultVirtualEnv | None = None
    venv_config: VirtualEnvConfig | None

    def __new__(cls) -> DefaultVirtualEnv:
        """
        Method that instantiates a singleton class and returns it.
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance.venv_config = None
            cls._instance = instance
        return cls._instance

    @classmethod
    def set_default_virtualenv_config(cls, venv_config: VirtualEnvConfig) -> None:
        """
        Set the default tools requirements configuration.
        """
        instance = cls._instance
        if instance is None:
            instance = cls()
        instance.venv_config = venv_config


class DefaultToolsPythonRequirements:
    """
    Simple class to hold registered imports.
    """

    _instance: DefaultToolsPythonRequirements | None = None
    config: DefaultConfig | None

    def __new__(cls) -> DefaultToolsPythonRequirements:
        """
        Method that instantiates a singleton class and returns it.
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance.config = None
            cls._instance = instance
        return cls._instance

    @classmethod
    def set_default_requirements_config(cls, config: DefaultConfig) -> None:
        """
        Set the default tools requirements configuration.
        """
        instance = cls._instance
        if instance is None:
            instance = cls()
        instance.config = config


class RegisteredImports:
    """
    Simple class to hold registered imports.
    """

    _instance: RegisteredImports | None = None
    _registered_imports: dict[str, VirtualEnvConfig | None]

    def __new__(cls) -> RegisteredImports:
        """
        Method that instantiates a singleton class and returns it.
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._registered_imports = {}
            cls._instance = instance
        return cls._instance

    @classmethod
    def register_import(
        cls, import_module: str, venv_config: VirtualEnvConfig | None = None
    ) -> None:
        """
        Register an import.
        """
        instance = cls()
        if import_module not in instance._registered_imports:
            instance._registered_imports[import_module] = venv_config

    def __iter__(self) -> Iterator[tuple[str, VirtualEnvConfig | None]]:
        """
        Return an iterator of all registered imports.
        """
        return iter(self._registered_imports.items())


class Parser:
    """
    Singleton parser class that wraps argparse.
    """

    _instance: Parser | None = None
    parser: ArgumentParser
    subparsers: _SubParsersAction[ArgumentParser]
    context: Context
    repo_root: pathlib.Path

    def __new__(cls) -> Parser:
        """
        Method that instantiates a singleton class and returns it.
        """
        if cls._instance is None:
            # Let's do a litle manual parsing so that we can set debug or quiet early
            debug = False
            quiet = False
            for arg in sys.argv[1:]:
                if not arg.startswith("-"):
                    break
                if arg in ("-q", "--quiet"):
                    quiet = True
                    break
                if arg in ("-d", "--debug"):
                    debug = True
                    break
            instance = super().__new__(cls)
            instance.repo_root = pathlib.Path.cwd()
            instance.context = Context(instance, debug=debug, quiet=quiet)
            instance.parser = argparse.ArgumentParser(
                prog="tools",
                description="Python Tools Scripts",
                epilog="These tools are discovered under `<repo-root>/tools`.",
                allow_abbrev=False,
                formatter_class=argparse.RawDescriptionHelpFormatter,
            )
            instance.parser.add_argument(
                "--version", action="version", version=__version__
            )
            log_group = instance.parser.add_argument_group("Logging")
            timestamp_meg = log_group.add_mutually_exclusive_group()
            timestamp_meg.add_argument(
                "--timestamps",
                "--ts",
                action="store_true",
                help="Add time stamps to logs",
                dest="timestamps",
            )
            timestamp_meg.add_argument(
                "--no-timestamps",
                "--nts",
                action="store_false",
                default=True,
                help="Remove time stamps from logs",
                dest="timestamps",
            )
            level_group = log_group.add_mutually_exclusive_group()
            level_group.add_argument(
                "--quiet",
                "-q",
                dest="quiet",
                action="store_true",
                default=False,
                help="Disable logging",
            )
            level_group.add_argument(
                "--debug",
                "-d",
                action="store_true",
                default=False,
                help="Show debug messages",
            )
            run_options = instance.parser.add_argument_group(
                "Run Subprocess Options",
                description="These options apply to ctx.run() calls",
            )
            run_options.add_argument(
                "--timeout",
                "--timeout-secs",
                default=None,
                type=int,
                help="Timeout in seconds for the command to finish.",
                metavar="SECONDS",
                dest="timeout_secs",
            )
            run_options.add_argument(
                "--no-output-timeout-secs",
                "--nots",
                default=None,
                type=int,
                help="Timeout if no output has been seen for the provided seconds.",
                metavar="SECONDS",
                dest="no_output_timeout_secs",
            )

            instance.subparsers = instance.parser.add_subparsers(
                title="Commands", dest="command", required=True
            )
            cls._instance = instance
        return cls._instance

    def _process_registered_tool_modules(self) -> None:
        default_config = DefaultToolsPythonRequirements().config
        if default_config:
            default_config.install(self.context)

        default_venv: VirtualEnv | AbstractContextManager[None]
        default_venv_config = DefaultVirtualEnv().venv_config
        if default_venv_config:
            if not default_venv_config.name:
                default_venv_config.name = "default"
            default_venv_config.add_as_extra_site_packages = True
            default_venv = VirtualEnv(ctx=self.context, config=default_venv_config)
        else:
            default_venv = nullcontext()
        with default_venv:
            for module_name, venv_config in RegisteredImports():
                venv: VirtualEnv | AbstractContextManager[None]
                if venv_config:
                    if not venv_config.name:
                        venv_config.name = module_name
                    venv = VirtualEnv(ctx=self.context, config=venv_config)
                else:
                    venv = nullcontext()
                with venv:
                    try:
                        importlib.import_module(module_name)
                    except ImportError as exc:
                        if os.environ.get("TOOLS_IGNORE_IMPORT_ERRORS", "0") == "0":
                            self.context.warn(
                                f"Could not import the registered tools module {module_name!r}: {exc}"
                            )

    def parse_args(self) -> None:
        """
        Parse CLI.
        """
        # Log the argv getting executed
        self.context.debug(f"Tools executing 'sys.argv': {sys.argv}")
        # Process registered imports to allow other modules to register commands
        self._process_registered_tool_modules()
        options = self.parser.parse_args()
        if options.quiet:
            self.context._quiet = True
            self.context._debug = False
            logging.root.setLevel(logging.CRITICAL + 1)
        elif options.debug:
            self.context._quiet = False
            self.context._debug = True
            logging.root.setLevel(logging.DEBUG)
            self.context.console.log_path = True
            self.context.console_stdout.log_path = True
        else:
            self.context._quiet = False
            self.context._debug = False
            logging.root.setLevel(logging.INFO)
        if options.timestamps:
            for handler in logging.root.handlers:
                handler.setFormatter(logs.TIMESTAMP_FORMATTER)
        else:
            for handler in logging.root.handlers:
                handler.setFormatter(logs.NO_TIMESTAMP_FORMATTER)
        self.options = options
        if "func" not in options:
            self.context.exit(1, "No command was passed.")
        log.debug("CLI parsed options %s", options)
        options.func(options)

    def __getattr__(self, attr: str) -> Any:  # noqa: ANN401
        """
        Proxy unknown attributes to the parser instance.
        """
        if attr == "options":
            return self.__getattribute__(attr)
        return getattr(self.parser, attr)


class GroupReference:
    """
    Simple class to hold tools command group names.

    These are comparable to how they would be invoked using the CLI.
    For example, ``tools vm create`` is stored as ``("tools", "vm", "create")``
    """

    _instance: GroupReference | None = None
    _commands: dict[tuple[str, ...], CommandGroup]

    def __new__(cls) -> GroupReference:
        """
        Method that instantiates a singleton class and returns it.
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._commands = {}
            cls._instance = instance
        return cls._instance

    @classmethod
    def add_command(cls, cli_name: tuple[str, ...], group: CommandGroup) -> None:
        """
        Add a tools command.
        """
        instance = cls()
        if cli_name not in instance._commands:
            instance._commands[cli_name] = group

    def __getitem__(self, item: tuple[str, ...]) -> CommandGroup:
        """
        Propogate getting a command parser to the underlying dict.
        """
        return self._commands[item]


class CommandGroup:
    """
    Command group which holds the available tool functions.
    """

    def __init__(
        self,
        name: str,
        help: str,
        description: str | None = None,
        parent: Parser | CommandGroup | list[str] | tuple[str] | str | None = None,
        venv_config: VirtualEnvConfig | None = None,
    ) -> None:
        self.name = name
        if description is None:
            description = help
        if parent is None:
            parent = Parser()
            GroupReference.add_command((name,), self)
        # We can also pass a string or list of strings that specify the parent commands.
        # This should help avoid circular imports
        if isinstance(parent, str):
            parent = [parent]
        if isinstance(parent, list):
            # NOTE: This means ordering of imports is important, but better than risking circular imports
            GroupReference.add_command((*parent, name), self)
            parent = GroupReference()[tuple(parent)]

        if venv_config is not None and venv_config.name is None:
            venv_config.name = self.name

        self.venv_config: VirtualEnvConfig | None = venv_config

        if TYPE_CHECKING:
            assert parent
        self.parser = parent.subparsers.add_parser(  # type: ignore[union-attr, has-type]
            name.replace("_", "-"),
            help=help,
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.subparsers = self.parser.add_subparsers(
            title="Commands",
            dest=f"{name.replace('-', '_')}_command",
        )
        self.context = parent.context  # type: ignore[union-attr, has-type]

    def command(  # noqa: ANN201,C901,PLR0912,PLR0915
        self,
        func: FunctionType | None = None,
        *,
        name: str | None = None,
        help: str | None = None,
        description: str | None = None,
        arguments: dict[str, ArgumentOptions] | None = None,
        venv_config: VirtualEnvConfig | None = None,
    ):
        """
        Register a sub-command in the command group.
        """
        if func is None:
            return partial(
                self.command,
                name=name,
                help=help,
                description=description,
                arguments=arguments,
                venv_config=venv_config,
            )

        func_name = func.__name__
        func_file = sys.modules[func.__module__].__file__
        if TYPE_CHECKING:
            assert func_file
        func_path = str(pathlib.Path(func_file).relative_to(self.context.repo_root))

        if name is None:
            name = func_name

        if description is None:
            description = inspect.getdoc(func)
        if help is None and description is not None:
            help = description.splitlines()[0]
        command = self.subparsers.add_parser(
            name=name,
            help=help,
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        signature = inspect.signature(func)

        if arguments is None:
            if len(signature.parameters) > 1:
                msg = (
                    f"'arguments' is a mandatory keyword argument to the '@{self.name}.command' "
                    "decorator when additional arguments(besides the required 'ctx' as first "
                    "argument) or keyword arguments are defined. Please update the decorated "
                    f"function {func_name!r} in {func_path!r}."
                )
                raise RuntimeError(msg)
            arguments = {}

        for key in arguments:
            if key not in signature.parameters:
                msg = (
                    "Only pass argument names or keyword argument names on the 'arguments' keyword "
                    f"for the '@{self.name}.command' decorated function {func_name!r} in {func_path!r} "
                    f"which are also present in it's signature, {key!r} is not present."
                )
                raise RuntimeError(msg)

        type_annotation = typing.get_type_hints(func)
        first_parameter_seen = False
        for parameter in signature.parameters.values():
            if first_parameter_seen is False:
                first_parameter_seen = True
                if parameter.name != "ctx":
                    msg = (
                        f"'ctx' is a mandatory first argument to the '@{self.name}.command' "
                        f"decorated function {func_name!r} in {func_path!r}."
                    )
                    raise RuntimeError(msg)
                continue
            if parameter.annotation is parameter.empty:
                # No typing annotations
                continue

            # Get the correct type for the parameter
            param_type = type_annotation[parameter.name]
            param_type_args = typing.get_args(param_type)
            if param_type_args:
                # This is something like typing.Optional[list[str]]
                # Let's unwrap it to the inner type, which, for the example
                # here is, list[str]
                param_type = param_type_args[0]

            if isinstance(param_type, GenericAlias):
                param_type = typing.get_args(param_type)[0]

            kwargs = cast(FullArgumentOptions, arguments.get(parameter.name) or {})
            if parameter.default is parameter.empty:
                # Positional argument
                kwargs["type"] = param_type
                command.add_argument(parameter.name, **kwargs)  # type: ignore[arg-type]
                continue

            if kwargs.get("nargs") == "*":
                # Positional argument
                kwargs["type"] = param_type
                command.add_argument(parameter.name, **kwargs)  # type: ignore[arg-type]
                continue

            # Keyword argument
            kwargs["dest"] = parameter.name
            if "type" not in kwargs:
                if param_type is not bool:
                    kwargs["type"] = param_type
                elif "action" not in kwargs:
                    action = None
                    if parameter.default is True:
                        action = "store_false"
                    elif parameter.default is False:
                        action = "store_true"
                    if action is not None:
                        kwargs["action"] = action

            kwargs["default"] = parameter.default
            if "help" in kwargs and parameter.default is not None:
                if not kwargs["help"].endswith("."):
                    kwargs["help"] += "."
                kwargs["help"] += " [default: %(default)s]"
            flags = kwargs.pop("flags", None)
            if flags is None:
                flags = [f"--{parameter.name.replace('_', '-')}"]
            log.debug("Adding Command %r. Flags: %s; KwArgs: %s", name, flags, kwargs)
            command.add_argument(*flags, **kwargs)  # type: ignore[arg-type]

        command.set_defaults(func=partial(self, func, venv_config=venv_config))
        return func

    def __getattr__(self, attr: str) -> Any:  # noqa: ANN401
        """
        Proxy unknown attributes to the parser instance.
        """
        return getattr(self.parser, attr)

    def __call__(
        self,
        func: Callable[..., None],
        options: Namespace,
        venv_config: VirtualEnvConfig | None = None,
    ) -> None:
        """
        Execute the selected tool function.
        """
        signature = inspect.signature(func)
        args = []
        kwargs = {}
        for name, parameter in signature.parameters.items():
            if parameter.annotation is parameter.empty:
                # No typing annotations
                continue
            if name in options:
                if parameter.default is parameter.empty:
                    args.append(getattr(options, name))
                else:
                    kwargs[name] = getattr(options, name)

        bound = signature.bind_partial(*args, **kwargs)
        venv: VirtualEnv | None = None
        if venv_config:
            if venv_config.name is None:
                venv_config.name = getattr(options, f"{self.name}_command")
            venv = VirtualEnv(ctx=self.context, config=venv_config)
        elif self.venv_config:
            venv = VirtualEnv(ctx=self.context, config=self.venv_config)
        if venv:
            with venv:
                previous_venv = self.context.venv
                try:
                    self.context.venv = venv
                    func(self.context, *bound.args, **bound.kwargs)
                finally:
                    self.context.venv = previous_venv
        else:
            func(self.context, *bound.args, **bound.kwargs)


def command_group(
    name: str,
    help: str,
    description: str | None = None,
    venv_config: VirtualEnvConfig | None = None,
    parent: Parser | CommandGroup | list[str] | tuple[str] | str | None = None,
) -> CommandGroup:
    """
    Create a new command group.
    """
    return CommandGroup(
        name, help, description=description, venv_config=venv_config, parent=parent
    )

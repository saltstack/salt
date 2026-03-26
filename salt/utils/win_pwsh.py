import logging
import re

import salt.modules.cmdmod
import salt.utils.json
from salt.exceptions import CommandExecutionError

# Standard Salt logging
log = logging.getLogger(__name__)

HAS_CLR = False
try:
    import clr
    from System import Exception as DotNetException

    HAS_CLR = True
except ImportError as e:
    log.debug(f"could not import clr, pythonnet is not available")

HAS_PWSH_SDK = False
try:
    PWSH_GAC_NAME = "System.Management.Automation, Version=3.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35"
    clr.AddReference(PWSH_GAC_NAME)
    from System.Management.Automation import (
        CommandNotFoundException,
        ParameterBindingException,
        PowerShell,
        RuntimeException,
    )

    HAS_PWSH_SDK = True
except Exception as e:
    log.debug(f"win_pwsh could not load PowerShell SDK: {e}")


def run_dict(cmd, cwd=None):
    """
    Execute the PowerShell command and return the data as a dictionary

    .. versionadded:: 3006.9

    Args:

        cmd (str,list): The PowerShell command to run

        cwd (str): The current working directory

    Returns:
        dict: A dictionary containing the output of the PowerShell command

    Raises:
        CommandExecutionError:
            If an error is encountered or the command does not complete
            successfully
    """
    if isinstance(cmd, list):
        cmd = " ".join(map(str, cmd))
    if "convertto-json" not in cmd.lower():
        cmd = f"{cmd} | ConvertTo-Json"
    if "progresspreference" not in cmd.lower():
        cmd = f"$ProgressPreference = 'SilentlyContinue'; {cmd}"
    ret = salt.modules.cmdmod.run_all(cmd=cmd, shell="powershell", cwd=cwd)

    if "pid" in ret:
        del ret["pid"]

    if ret.get("stderr", ""):
        error = ret["stderr"].splitlines()[0]
        raise CommandExecutionError(error, info=ret)

    if "retcode" not in ret or ret["retcode"] != 0:
        # run_all logs an error to log.error, fail hard back to the user
        raise CommandExecutionError("Issue executing PowerShell cmd", info=ret)

    # Sometimes Powershell returns an empty string, which isn't valid JSON
    if ret["stdout"] == "":
        ret["stdout"] = "{}"

    try:
        ret = salt.utils.json.loads(ret["stdout"], strict=False)
    except ValueError:
        raise CommandExecutionError("No JSON results from PowerShell", info=ret)

    return ret


class PowerShellSession:
    """
    A stateful PowerShell runspace backed by the .NET PowerShell SDK
    (``System.Management.Automation``), loaded via ``pythonnet``.

    Unlike :func:`run_dict`, which shells out to a ``powershell.exe``
    subprocess, this class opens an **in-process** runspace and keeps it alive
    across multiple calls.  The same runspace is reused for every ``run*``
    invocation, so imported modules, loaded functions, and session variables
    persist for the lifetime of the object.

    **Requirements:** both :data:`HAS_CLR` and :data:`HAS_PWSH_SDK` must be
    ``True`` before instantiating this class.

    **Usage — always use as a context manager** so the underlying runspace is
    disposed of deterministically::

        with PowerShellSession() as session:
            result = session.run_json("Get-NetAdapter | Select-Object Name, Status")

    **Methods:**

    * :meth:`run` — run a script and return raw Python scalars/lists.
    * :meth:`run_json` — run a script and return a parsed Python object via
      ``ConvertTo-Json``.
    * :meth:`run_strict` — like :meth:`run` but raises
      :exc:`~salt.exceptions.CommandExecutionError` if the script did not run
      to completion (i.e., an uncaught error occurred).

    **Session defaults** set in :meth:`__init__`:

    * ``$ErrorActionPreference = 'Stop'`` — all non-terminating cmdlet errors
      are promoted to terminating exceptions so they cannot be silently ignored.
    * ``$ProgressPreference = 'SilentlyContinue'`` — suppresses progress bars
      that would otherwise pollute the output stream.
    * ``$WarningPreference = 'SilentlyContinue'`` — suppresses advisory
      warnings that are not actionable in an automation context.
    """

    def __init__(self):
        """
        Create the PowerShell runspace and apply session-wide preferences.

        Sets ``$ErrorActionPreference = 'Stop'`` so every cmdlet uses
        terminating-error semantics by default.  Individual commands that are
        expected to return nothing (e.g., ``Get-NetRoute`` when no route
        exists) must use ``-ErrorAction SilentlyContinue`` or be wrapped in a
        PowerShell ``try/catch`` block.
        """
        # Create PowerShell instance
        self.ps = PowerShell.Create()

        # Suppress anything that might be displayed
        self.ps.AddScript("$ProgressPreference = 'SilentlyContinue'").AddStatement()
        self.ps.AddScript("$ErrorActionPreference = 'Stop'").AddStatement()
        self.ps.AddScript("$WarningPreference = 'SilentlyContinue'").AddStatement()
        self.ps.Invoke()

    def __enter__(self):
        return self

    def version(self):
        return self.run("$PSVersionTable.PSVersion.ToString()")

    def import_modules(self, modules=None):
        """
        Load modules into the existing session
        """
        if not modules:
            return

        self.ps.Commands.Clear()
        self.ps.Streams.ClearStreams()
        for module in modules if isinstance(modules, list) else [modules]:
            self.ps.AddScript(f"Import-Module {module}").AddStatement()
        self.ps.Invoke()

    def run(self, cmd):
        """
        Run a PowerShell command and return the result without attempting to
        parse it convert the PowerShell objects.

        Args:

            cmd (str): The command to run.

        Returns:
            str: A string with the results of the command
            list: If there is more than one return, it will be a list of strings
        """
        # Clear previous commands and any accumulated stream state
        self.ps.Commands.Clear()
        self.ps.Streams.ClearStreams()
        self.ps.AddScript(cmd)
        results = self.ps.Invoke()

        if self.ps.HadErrors:
            error_msg = "Unknown PowerShell Error"

            if self.ps.Streams.Error.Count > 0:
                error_msg = self.ps.Streams.Error[0].ToString()
            elif self.ps.InvocationStateInfo.Reason:
                error_msg = str(self.ps.InvocationStateInfo.Reason.Message)

            # We don't raise here so the session stays alive, but we log it
            log.debug(f"PowerShell Session Warning/Error: {error_msg}")
            return error_msg

        if not results or len(results) == 0:
            return None

        if len(results) == 1:
            value = results[0]
            if value is None:
                return None

            # Access the underlying .NET BaseObject (e.g., System.String -> str)
            base_value = value.BaseObject

            # Basic type mapping
            if isinstance(base_value, (str, int, bool, float)):
                return base_value

            return str(base_value)

        # If there are multiple results, return them as a list of strings
        return [str(result) for result in results]

    def run_json(self, cmd, depth=4):
        """
        Run a PowerShell command and return the result as a parsed Python object.

        Unless the command already contains ``ConvertTo-Json``, the method
        automatically pipes the output through ``ConvertTo-Json -Compress
        -Depth <depth>`` and then ``Out-String`` before parsing. This ensures
        that PowerShell objects are always serialized to English-language JSON
        regardless of the system locale.

        Args:

            cmd (str): The PowerShell command or script to run.

            depth (int): The JSON serialization depth passed to
                ``ConvertTo-Json``. Defaults to ``4``.

        Returns:
            Any: The deserialized Python object (dict, list, str, etc.), or
            ``None`` if PowerShell produced no output.

        Raises:
            CommandExecutionError: If PowerShell enters a ``Failed`` state.
        """
        # Clear previous commands and any accumulated stream state
        self.ps.Commands.Clear()
        self.ps.Streams.ClearStreams()

        self.ps.AddScript(cmd)

        # Only add ConvertTo-Json if not already present in the command.
        # Match both piped (| ConvertTo-Json) and standalone (ConvertTo-Json
        # -InputObject ...) forms so we never double-encode the output.
        if not re.search(r"ConvertTo-Json", cmd, re.IGNORECASE):
            self.ps.AddCommand("ConvertTo-Json")
            self.ps.AddParameter("Compress", True)
            self.ps.AddParameter("Depth", depth)

        # Use Out-String for reliable string extraction from the pipeline
        if not cmd.lower().endswith("out-string"):
            self.ps.AddCommand("Out-String")

        results = self.ps.Invoke()

        if self.ps.HadErrors:
            if self.ps.InvocationStateInfo.State.ToString() == "Failed":
                err_msgs = [str(err) for err in self.ps.Streams.Error]
                raise CommandExecutionError(f"PowerShell Error: {err_msgs}")

        if results and len(results) > 0:
            return salt.utils.json.loads(str(results[0]))
        return None

    def run_strict(self, cmd):
        """
        Run a PowerShell command and raise on any error.

        Identical to :meth:`run` except that a ``CommandExecutionError`` is
        raised when PowerShell reports ``HadErrors``, rather than logging and
        returning the error string. Use this when the caller must not silently
        continue after a failure (e.g., when executing a large configuration
        script where a mid-script error would leave the system in an unknown
        state).

        .. note::
            PowerShell sets ``HadErrors = True`` even for errors caught by
            ``try/catch`` inside the script.  To distinguish "script ran to
            completion with some suppressed errors" from "script terminated
            mid-way", we bracket the caller's script with a sentinel variable.
            If the sentinel is ``$true`` at the end, all errors were caught
            intentionally and we do not raise.

        Args:

            cmd (str): The PowerShell command or script to run.

        Returns:
            str | list | None: Same return types as :meth:`run`.

        Raises:
            CommandExecutionError: If PowerShell reports any error.
        """
        self.ps.Commands.Clear()
        self.ps.Streams.ClearStreams()
        # Sentinel: set $false before the script, $true after.  If the script
        # terminates mid-way (uncaught error) the sentinel stays $false.
        wrapped = "$__salt_ok__ = $false\n" + cmd + "\n$__salt_ok__ = $true"
        self.ps.AddScript(wrapped)
        results = self.ps.Invoke()

        if self.ps.HadErrors:
            # Capture error info BEFORE the sentinel query overwrites state.
            streams_err = (
                self.ps.Streams.Error[0].ToString()
                if self.ps.Streams.Error.Count > 0
                else None
            )
            inv_reason = self.ps.InvocationStateInfo.Reason

            # Did the script run to completion?  If yes, every error was caught
            # by an explicit try/catch inside the script — do not raise.
            self.ps.Commands.Clear()
            self.ps.Streams.ClearStreams()
            self.ps.AddScript("$__salt_ok__ -eq $true")
            chk = self.ps.Invoke()
            ran_to_end = (
                chk and chk.Count > 0 and str(chk[0]).lower() == "true"
            )
            if ran_to_end:
                # All errors were intentionally suppressed; script completed.
                pass
            else:
                # Script terminated before the sentinel — uncaught error.
                error_msg = "Unknown PowerShell Error"
                if streams_err:
                    error_msg = streams_err
                elif inv_reason:
                    error_msg = str(inv_reason.Message)
                else:
                    # Terminating errors from $ErrorActionPreference = 'Stop'
                    # do not always populate Streams.Error in PS 5.1 SDK.
                    # Query $Error[0] from the runspace as a last-resort.
                    self.ps.Commands.Clear()
                    self.ps.AddScript(
                        "if ($Error.Count -gt 0)"
                        " { $Error[0].Exception.Message } else { '' }"
                    )
                    err_results = self.ps.Invoke()
                    if err_results and err_results.Count > 0:
                        msg = str(err_results[0])
                        if msg.strip():
                            error_msg = msg
                raise CommandExecutionError(error_msg)

        if not results or len(results) == 0:
            return None

        if len(results) == 1:
            value = results[0]
            if value is None:
                return None
            base_value = value.BaseObject
            if isinstance(base_value, (str, int, bool, float)):
                return base_value
            return str(base_value)

        return [str(result) for result in results]

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        exc_type: The class of the exception (e.g., CommandExecutionError)
        exc_val: The instance of the exception
        exc_tb: The traceback object
        """
        if exc_type:
            log.debug(f"PowerShellSession exiting due to error: {exc_val}")
            log.debug(exc_tb)
        self.ps.Dispose()

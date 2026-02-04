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
except ImportError as e:
    log.debug(f"could not import clr, pythonnet is not available")
    HAS_CLR = False

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
    def __init__(self):
        """
        Set up the session. Suppress progress bars and warnings
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

        # Preload modules and set preferences once
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
        # Clear previous commands but keep the Runspace/Session alive
        self.ps.Commands.Clear()
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
        # Clear previous commands but keep the Runspace/Session alive
        self.ps.Commands.Clear()

        # Add script
        self.ps.AddScript(cmd)

        # Only add ConvertTo-Json if not already there
        # We use -Compress to keep the string small and -Depth to ensure nested data isn't lost
        if not re.search(
            pattern=r"\|\s*ConvertTo-Json", string=cmd, flags=re.IGNORECASE
        ):
            self.ps.AddCommand("ConvertTo-Json")
            self.ps.AddParameter("Compress", True)
            self.ps.AddParameter("Depth", depth)

        # Use Out-String for better python handling
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        exc_type: The class of the exception (e.g., CommandExecutionError)
        exc_val: The instance of the exception
        exc_tb: The traceback object
        """
        if exc_type:
            log.debug(f"PowerShellSession exiting du to error: {exc_val}")
            log.debug(exc_tb)
        self.ps.Dispose()

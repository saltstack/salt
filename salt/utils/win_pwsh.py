import salt.modules.cmdmod
import salt.utils.json
import salt.utils.platform
from salt.exceptions import CommandExecutionError

__virtualname__ = "win_pwsh"


def __virtual__():
    """
    Only load if windows
    """
    if not salt.utils.platform.is_windows():
        return False, "This utility will only run on Windows"

    return __virtualname__


def run_dict(cmd, cwd=None):
    """
    Execute the powershell command and return the data as a dictionary

    Args:

        cmd (str): The powershell command to run

        cwd (str): The current working directory

    Returns:
        dict: A dictionary containing the output of the powershell command

    Raises:
        CommandExecutionError:
            If an error is encountered or the command does not complete
            successfully
    """
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

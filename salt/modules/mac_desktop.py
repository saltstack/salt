"""
macOS implementations of various commands in the "desktop" interface
"""

import salt.utils.platform
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = "desktop"


def __virtual__():
    """
    Only load on Mac systems
    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return False, "Cannot load macOS desktop module: This is not a macOS host."


def get_output_volume():
    """
    Get the output volume (range 0 to 100)

    CLI Example:

    .. code-block:: bash

        salt '*' desktop.get_output_volume
    """
    cmd = 'osascript -e "get output volume of (get volume settings)"'
    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)
    _check_cmd(call)

    return call.get("stdout")


def set_output_volume(volume):
    """
    Set the volume of sound.

    volume
        The level of volume. Can range from 0 to 100.

    CLI Example:

    .. code-block:: bash

        salt '*' desktop.set_output_volume <volume>
    """
    cmd = f'osascript -e "set volume output volume {volume}"'
    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)
    _check_cmd(call)

    return get_output_volume()


def screensaver():
    """
    Launch the screensaver.

    CLI Example:

    .. code-block:: bash

        salt '*' desktop.screensaver
    """
    cmd = "open /System/Library/Frameworks/ScreenSaver.framework/Versions/A/Resources/ScreenSaverEngine.app"
    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)
    _check_cmd(call)

    return True


def lock():
    """
    Lock the desktop session

    CLI Example:

    .. code-block:: bash

        salt '*' desktop.lock
    """
    cmd = (
        "/System/Library/CoreServices/Menu\\"
        " Extras/User.menu/Contents/Resources/CGSession -suspend"
    )
    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)
    _check_cmd(call)

    return True


def say(*words):
    """
    Say some words.

    words
        The words to execute the say command with.

    CLI Example:

    .. code-block:: bash

        salt '*' desktop.say <word0> <word1> ... <wordN>
    """
    cmd = "say {}".format(" ".join(words))
    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)
    _check_cmd(call)

    return True


def _check_cmd(call):
    """
    Check the output of the cmd.run_all function call.
    """
    if call["retcode"] != 0:
        comment = ""
        std_err = call.get("stderr")
        std_out = call.get("stdout")
        if std_err:
            comment += std_err
        if std_out:
            comment += std_out

        raise CommandExecutionError(f"Error running command: {comment}")

    return call

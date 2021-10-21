"""
    tasks.utils
    ~~~~~~~~~~~

    Invoke utilities
"""

import sys

try:
    from blessings import Terminal

    try:
        terminal = Terminal()
        HAS_BLESSINGS = True
    except Exception:  # pylint: disable=broad-except
        terminal = None
        HAS_BLESSINGS = False
except ImportError:
    terminal = None
    HAS_BLESSINGS = False


def exit_invoke(exitcode, message=None, *args, **kwargs):
    if message is not None:
        if exitcode > 0:
            warn(message, *args, **kwargs)
        else:
            info(message, *args, **kwargs)
    sys.exit(exitcode)


def info(message, *args, **kwargs):
    if not isinstance(message, str):
        message = str(message)
    message = message.format(*args, **kwargs)
    if terminal:
        message = terminal.bold(terminal.green(message))
    write_message(message)


def warn(message, *args, **kwargs):
    if not isinstance(message, str):
        message = str(message)
    message = message.format(*args, **kwargs)
    if terminal:
        message = terminal.bold(terminal.yellow(message))
    write_message(message)


def error(message, *args, **kwargs):
    if not isinstance(message, str):
        message = str(message)
    message = message.format(*args, **kwargs)
    if terminal:
        message = terminal.bold(terminal.red(message))
    write_message(message)


def write_message(message):
    sys.stderr.write(message)
    if not message.endswith("\n"):
        sys.stderr.write("\n")
    sys.stderr.flush()

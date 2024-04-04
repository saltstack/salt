"""
Functions for working with the codepage on Windows systems
"""

import logging
from contextlib import contextmanager

from salt.exceptions import CodePageError

log = logging.getLogger(__name__)

try:
    import pywintypes
    import win32console

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# Although utils are often directly imported, it is also possible to use the loader.
def __virtual__():
    """
    Only load if Win32 Libraries are installed
    """
    if not HAS_WIN32:
        return False, "This utility requires pywin32"

    return "win_chcp"


@contextmanager
def chcp(page_id, raise_error=False):
    """
    Gets or sets the codepage of the shell.

    Args:

        page_id (str, int):
            A number representing the codepage.

        raise_error (bool):
            ``True`` will raise an error if the codepage fails to change.
            ``False`` will suppress the error

    Returns:
        int: A number representing the codepage

    Raises:
        CodePageError: On unsuccessful codepage change
    """
    if not isinstance(page_id, int):
        try:
            page_id = int(page_id)
        except ValueError:
            error = f"The `page_id` needs to be an integer, not {type(page_id)}"
            if raise_error:
                raise CodePageError(error)
            log.error(error)
            return -1

    previous_page_id = get_codepage_id(raise_error=raise_error)

    if page_id and previous_page_id and page_id != previous_page_id:
        set_code_page = True
    else:
        set_code_page = False

    try:
        if set_code_page:
            set_codepage_id(page_id, raise_error=raise_error)

        # Subprocesses started from now will use the set code page id
        yield
    finally:
        if set_code_page:
            # Reset to the old code page
            set_codepage_id(previous_page_id, raise_error=raise_error)


def get_codepage_id(raise_error=False):
    """
    Get the currently set code page on windows

    Args:

        raise_error (bool):
            ``True`` will raise an error if the codepage fails to change.
            ``False`` will suppress the error

    Returns:
        int: A number representing the codepage

    Raises:
        CodePageError: On unsuccessful codepage change
    """
    try:
        return win32console.GetConsoleCP()
    except pywintypes.error as exc:
        _, _, msg = exc.args
        error = f"Failed to get the windows code page: {msg}"
        if raise_error:
            raise CodePageError(error)
        else:
            log.error(error)
        return -1


def set_codepage_id(page_id, raise_error=False):
    """
    Set the code page on windows

    Args:

        page_id (str, int):
            A number representing the codepage.

        raise_error (bool):
            ``True`` will raise an error if the codepage fails to change.
            ``False`` will suppress the error

    Returns:
        int: A number representing the codepage

    Raises:
        CodePageError: On unsuccessful codepage change
    """
    if not isinstance(page_id, int):
        try:
            page_id = int(page_id)
        except ValueError:
            error = f"The `page_id` needs to be an integer, not {type(page_id)}"
            if raise_error:
                raise CodePageError(error)
            log.error(error)
            return -1
    try:
        win32console.SetConsoleCP(page_id)
        return get_codepage_id(raise_error=raise_error)
    except pywintypes.error as exc:
        _, _, msg = exc.args
        error = f"Failed to set the windows code page: {msg}"
        if raise_error:
            raise CodePageError(error)
        else:
            log.error(error)
        return -1

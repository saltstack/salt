"""
Functions for working with the codepage on Windows systems
"""

import logging
import string
import subprocess
from contextlib import contextmanager

from salt.exceptions import CodePageError

log = logging.getLogger(__name__)


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
    if page_id is not None:
        if not isinstance(page_id, int):
            page_id = int(page_id)
    else:
        page_id = get_page_id(raise_error=raise_error)

    previous_page_id = get_page_id(raise_error=raise_error)

    if page_id and previous_page_id and page_id != previous_page_id:
        set_code_page = True
    else:
        set_code_page = False

    try:
        if set_code_page:
            set_page_id(page_id, raise_error=raise_error)

        # Subprocesses started from now will use the set code page id
        yield
    finally:
        if set_code_page:
            # Reset to the old code page
            set_page_id(previous_page_id, raise_error=raise_error)


def get_page_id(raise_error=False):
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
    proc = subprocess.run(
        "chcp.com",
        timeout=10,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        error = "Failed to get the windows code page: {}".format(proc)
        if raise_error:
            raise CodePageError(error)
        else:
            log.error(error)
    else:
        codepage = "".join([char for char in proc.stdout if char in string.digits])
        if codepage:
            return int(codepage)
    return -1


def set_page_id(page_id, raise_error=False):
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
    proc = subprocess.run(
        "chcp.com {}".format(page_id),
        timeout=10,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        error = "Failed to set the windows code page: {}".format(proc)
        if raise_error:
            raise CodePageError(error)
        else:
            log.error(error)
    else:
        codepage = "".join([char for char in proc.stdout if char in string.digits])
        if codepage:
            return int(codepage)
    return -1

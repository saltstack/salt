"""
Functions for working with the codepage on Windows systems
"""

# Import Python libs
import logging
import string
import subprocess

log = logging.getLogger(__name__)


class CodePageError(Exception):
    pass


def chcp(page_id=None, raise_error=False):
    """
    Gets or sets the codepage of the shell.

    Args:

        page_id (str, int):
            A number representing the codepage. Default is ``None``

        raise_error (bool):
            ``True`` will raise an error if the codepage fails to change.
            ``False`` will suppress the error

    Returns:
        str: A number representing the codepage

    Raises:
        CodePageError: On unsuccessful codepage change
    """
    # check if codepage needs to change
    if page_id is not None:
        page_id = str(page_id)
        current_page = chcp()
        if current_page == page_id:
            return current_page
    else:
        page_id = ""

    # change or get codepage
    try:
        chcp_process = subprocess.Popen(
            "chcp.com {}".format(page_id),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        log.error("Code Page was not found!")
        return ""

    # get codepage id
    chcp_ret = chcp_process.communicate(timeout=10)[0].decode("ascii", "ignore")
    chcp_ret = "".join([c for c in chcp_ret if c in string.digits])

    # check if codepage changed
    if page_id != "":
        if page_id != chcp_ret:
            if raise_error:
                raise CodePageError()
            else:
                log.error("Code page failed to change to %s!", page_id)

    # If nothing returned, return the current codepage
    if chcp_ret == "":
        chcp_ret = chcp()

    log.debug("Code page is %s", chcp_ret)
    return chcp_ret

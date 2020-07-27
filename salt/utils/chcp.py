# -*- coding: utf-8 -*-

"""
Change the code page for the Windows shell
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
    Changes or gets the code page of the shell.
    :param page_id: None or int or str
    :param raise_error: bool
    :return: str: code page id
    :raises: CodePageError
    """
    # check if code page needs to change
    if page_id is not None:
        page_id = str(page_id)
        current_page = chcp()
        if current_page == page_id:
            return current_page
    else:
        page_id = ""

    # change or get code page
    try:
        chcp_process = subprocess.Popen("chcp.com {}".format(page_id), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        log.error("Code Page was not found!")
        return ""

    # get code page id
    chcp_ret = chcp_process.communicate(timeout=10)[0].decode("ascii", "ignore")
    chcp_ret = "".join([c for c in chcp_ret if c in string.digits])

    # check if code page changed
    if page_id != "":
        if page_id != chcp_ret:
            if raise_error:
                raise CodePageError()
            else:
                log.error("Code page failed to change to %s!", page_id)

    if chcp_ret == "":
        chcp_ret = chcp()

    log.debug("Code page is %s", chcp_ret)
    return chcp_ret

# -*- coding: utf-8 -*-
import logging

log = logging.getLogger(__name__)


def get_retcode(ret):
    '''
    Determine a retcode for a given return
    '''
    retcode = 0
    # if there is a dict with retcode, use that
    if isinstance(ret, dict) and ret.get('retcode', 0) != 0:
        return ret['retcode']
    # if its a boolean, False means 1
    elif isinstance(ret, bool) and not ret:
        return 1
    return retcode

# vim:set et sts=4 ts=4 tw=80:

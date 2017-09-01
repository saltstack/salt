# -*- coding: utf-8 -*-
'''
Utility functions for state functions

.. versionadded:: Oxygen
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt libs
from salt.ext import six
import salt.state

_empty = object()


def gen_tag(low):
    '''
    Generate the running dict tag string from the low data structure
    '''
    return '{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(low)


def search_onfail_requisites(sid, highstate):
    '''
    For a particular low chunk, search relevant onfail related states
    '''
    onfails = []
    if '_|-' in sid:
        st = salt.state.split_low_tag(sid)
    else:
        st = {'__id__': sid}
    for fstate, fchunks in six.iteritems(highstate):
        if fstate == st['__id__']:
            continue
        else:
            for mod_, fchunk in six.iteritems(fchunks):
                if (
                    not isinstance(mod_, six.string_types) or
                    mod_.startswith('__')
                ):
                    continue
                else:
                    if not isinstance(fchunk, list):
                        continue
                    else:
                        # bydefault onfail will fail, but you can
                        # set onfail_stop: False to prevent the highstate
                        # to stop if you handle it
                        onfail_handled = False
                        for fdata in fchunk:
                            if not isinstance(fdata, dict):
                                continue
                            onfail_handled = (fdata.get('onfail_stop', True)
                                              is False)
                            if onfail_handled:
                                break
                        if not onfail_handled:
                            continue
                        for fdata in fchunk:
                            if not isinstance(fdata, dict):
                                continue
                            for knob, fvalue in six.iteritems(fdata):
                                if knob != 'onfail':
                                    continue
                                for freqs in fvalue:
                                    for fmod, fid in six.iteritems(freqs):
                                        if not (
                                            fid == st['__id__'] and
                                            fmod == st.get('state', fmod)
                                        ):
                                            continue
                                        onfails.append((fstate, mod_, fchunk))
    return onfails


def check_onfail_requisites(state_id, state_result, running, highstate):
    '''
    When a state fail and is part of a highstate, check
    if there is onfail requisites.
    When we find onfail requisites, we will consider the state failed
    only if at least one of those onfail requisites also failed

    Returns:

        True: if onfail handlers suceeded
        False: if one on those handler failed
        None: if the state does not have onfail requisites

    '''
    nret = None
    if (
        state_id and state_result and
        highstate and isinstance(highstate, dict)
    ):
        onfails = search_onfail_requisites(state_id, highstate)
        if onfails:
            for handler in onfails:
                fstate, mod_, fchunk = handler
                for rstateid, rstate in six.iteritems(running):
                    if '_|-' in rstateid:
                        st = salt.state.split_low_tag(rstateid)
                    # in case of simple state, try to guess
                    else:
                        id_ = rstate.get('__id__', rstateid)
                        if not id_:
                            raise ValueError('no state id')
                        st = {'__id__': id_, 'state': mod_}
                    if mod_ == st['state'] and fstate == st['__id__']:
                        ofresult = rstate.get('result', _empty)
                        if ofresult in [False, True]:
                            nret = ofresult
                        if ofresult is False:
                            # as soon as we find an errored onfail, we stop
                            break
                # consider that if we parsed onfailes without changing
                # the ret, that we have failed
                if nret is None:
                    nret = False
    return nret


def check_result(running, recurse=False, highstate=None):
    '''
    Check the total return value of the run and determine if the running
    dict has any issues
    '''
    if not isinstance(running, dict):
        return False

    if not running:
        return False

    ret = True
    for state_id, state_result in six.iteritems(running):
        if not recurse and not isinstance(state_result, dict):
            ret = False
        if ret and isinstance(state_result, dict):
            result = state_result.get('result', _empty)
            if result is False:
                ret = False
            # only override return value if we are not already failed
            elif result is _empty and isinstance(state_result, dict) and ret:
                ret = check_result(
                    state_result, recurse=True, highstate=highstate)
        # if we detect a fail, check for onfail requisites
        if not ret:
            # ret can be None in case of no onfail reqs, recast it to bool
            ret = bool(check_onfail_requisites(state_id, state_result,
                                               running, highstate))
        # return as soon as we got a failure
        if not ret:
            break
    return ret

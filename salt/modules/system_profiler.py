# -*- coding: utf-8 -*-
'''
System Profiler Module

Interface with Mac OSX's command-line System Profiler utility to get
information about package receipts and installed applications.

.. versionadded:: 2015.5.0

'''

from __future__ import absolute_import

import plistlib
import subprocess
import salt.utils
from salt.ext import six

PROFILER_BINARY = '/usr/sbin/system_profiler'


def __virtual__():
    '''
    Check to see if the system_profiler binary is available
    '''
    PROFILER_BINARY = salt.utils.which('system_profiler')

    if PROFILER_BINARY:
        return True
    else:
        return False


def _call_system_profiler(datatype):
    '''
    Call out to system_profiler.  Return a dictionary
    of the stuff we are interested in.
    '''

    p = subprocess.Popen(
        [PROFILER_BINARY, '-detailLevel', 'full',
         '-xml', datatype], stdout=subprocess.PIPE)
    (sysprofresults, sysprof_stderr) = p.communicate(input=None)

    if six.PY2:
        plist = plistlib.readPlistFromString(sysprofresults)
    else:
        plist = plistlib.readPlistFromBytes(sysprofresults)

    try:
        apps = plist[0]['_items']
    except (IndexError, KeyError):
        apps = []

    return apps


def receipts():
    '''
    Return the results of a call to
    ``system_profiler -xml -detail full SPInstallHistoryDataType``
    as a dictionary.  Top-level keys of the dictionary
    are the names of each set of install receipts, since
    there can be multiple receipts with the same name.
    Contents of each key are a list of dictionaries.

    CLI Example:

    .. code-block:: bash

        salt '*' systemprofiler.receipts
    '''

    apps = _call_system_profiler('SPInstallHistoryDataType')

    appdict = {}

    for a in apps:
        details = dict(a)
        details.pop('_name')
        if 'install_date' in details:
            details['install_date'] = details['install_date'].strftime('%Y-%m-%d %H:%M:%S')
        if 'info' in details:
            try:
                details['info'] = '{0}: {1}'.format(details['info'][0],
                                                    details['info'][1].strftime('%Y-%m-%d %H:%M:%S'))
            except (IndexError, AttributeError):
                pass

        if a['_name'] not in appdict:
            appdict[a['_name']] = []

        appdict[a['_name']].append(details)

    return appdict


def applications():
    '''
    Return the results of a call to
    ``system_profiler -xml -detail full SPApplicationsDataType``
    as a dictionary.  Top-level keys of the dictionary
    are the names of each set of install receipts, since
    there can be multiple receipts with the same name.
    Contents of each key are a list of dictionaries.

    Note that this can take a long time depending on how many
    applications are installed on the target Mac.

    CLI Example:

    .. code-block:: bash

        salt '*' systemprofiler.applications
    '''

    apps = _call_system_profiler('SPApplicationsDataType')

    appdict = {}

    for a in apps:
        details = dict(a)
        details.pop('_name')
        if 'lastModified' in details:
            details['lastModified'] = details['lastModified'].strftime('%Y-%m-%d %H:%M:%S')
        if 'info' in details:
            try:
                details['info'] = '{0}: {1}'.format(details['info'][0],
                                                    details['info'][1].strftime('%Y-%m-%d %H:%M:%S'))
            except (IndexError, AttributeError):
                pass

        if a['_name'] not in appdict:
            appdict[a['_name']] = []

        appdict[a['_name']].append(details)

    return appdict

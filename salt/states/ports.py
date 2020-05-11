# -*- coding: utf-8 -*-
'''
Manage software from FreeBSD ports

.. versionadded:: 2014.1.0

.. note::

    It may be helpful to use a higher timeout when running a
    :mod:`ports.installed <salt.states.ports>` state, since compiling the port
    may exceed Salt's timeout.

    .. code-block:: bash

        salt -t 1200 '*' state.highstate
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import copy
import logging
import sys

# Import salt libs
import salt.utils.data
from salt.exceptions import SaltInvocationError, CommandExecutionError
from salt.modules.freebsdports import _normalize, _options_file_exists

# Needed by imported function _options_file_exists
import os  # pylint: disable=W0611
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    if __grains__.get('os', '') == 'FreeBSD' and 'ports.install' in __salt__:
        return 'ports'
    return False


def _repack_options(options):
    '''
    Repack the options data
    '''
    return dict(
        [
            (six.text_type(x), _normalize(y))
            for x, y in six.iteritems(salt.utils.data.repack_dictlist(options))
        ]
    )


def _get_option_list(options):
    '''
    Returns the key/value pairs in the passed dict in a commaspace-delimited
    list in the format "key=value".
    '''
    return ', '.join(['{0}={1}'.format(x, y) for x, y in six.iteritems(options)])


def _build_option_string(options):
    '''
    Common function to get a string to append to the end of the state comment
    '''
    if options:
        return ('with the following build options: {0}'
                .format(_get_option_list(options)))
    else:
        return 'with the default build options'


def installed(name, options=None):
    '''
    Verify that the desired port is installed, and that it was compiled with
    the desired options.

    options
        Make sure that the desired non-default options are set

        .. warning::

            Any build options not passed here assume the default values for the
            port, and are not just differences from the existing cached options
            from a previous ``make config``.

    Example usage:

    .. code-block:: yaml

        security/nmap:
          ports.installed:
            - options:
              - IPV6: off
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': '{0} is already installed'.format(name)}
    try:
        current_options = __salt__['ports.showconfig'](name, default=False,
                                                       dict_return=True)
        default_options = __salt__['ports.showconfig'](name, default=True,
                                                       dict_return=True)
        # unpack the options from the top-level return dict
        if current_options:
            current_options = current_options[next(iter(current_options))]
        if default_options:
            default_options = default_options[next(iter(default_options))]
    except (SaltInvocationError, CommandExecutionError) as exc:
        ret['result'] = False
        ret['comment'] = ('Unable to get configuration for {0}. Port name may '
                          'be invalid, or ports tree may need to be updated. '
                          'Error message: {1}'.format(name, exc))
        return ret

    options = _repack_options(options) if options is not None else {}
    desired_options = copy.deepcopy(default_options)
    desired_options.update(options)
    ports_pre = [
        x['origin'] for x in
        six.itervalues(__salt__['pkg.list_pkgs'](with_origin=True))
    ]

    if current_options == desired_options and name in ports_pre:
        # Port is installed as desired
        if options:
            ret['comment'] += ' ' + _build_option_string(options)
        return ret

    if not default_options:
        if options:
            ret['result'] = False
            ret['comment'] = ('{0} does not have any build options, yet '
                              'options were specified'.format(name))
            return ret
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = '{0} will be installed'.format(name)
                return ret
    else:
        bad_opts = [x for x in options if x not in default_options]
        if bad_opts:
            ret['result'] = False
            ret['comment'] = ('The following options are not available for '
                              '{0}: {1}'.format(name, ', '.join(bad_opts)))
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = '{0} will be installed '.format(name)
            ret['comment'] += _build_option_string(options)
            return ret

        if options:
            if not __salt__['ports.config'](name, reset=True, **options):
                ret['result'] = False
                ret['comment'] = 'Unable to set options for {0}'.format(name)
                return ret
        else:
            __salt__['ports.rmconfig'](name)
            if _options_file_exists(name):
                ret['result'] = False
                ret['comment'] = 'Unable to clear options for {0}'.format(name)
                return ret

    ret['changes'] = __salt__['ports.install'](name)
    ports_post = [
        x['origin'] for x in
        six.itervalues(__salt__['pkg.list_pkgs'](with_origin=True))
    ]
    err = sys.modules[
        __salt__['test.ping'].__module__
    ].__context__.pop('ports.install_error', None)
    if err or name not in ports_post:
        ret['result'] = False
    if ret['result']:
        ret['comment'] = 'Successfully installed {0}'.format(name)
        if default_options:
            ret['comment'] += ' ' + _build_option_string(options)
    else:
        ret['comment'] = 'Failed to install {0}'.format(name)
        if err:
            ret['comment'] += '. Error message:\n{0}'.format(err)
    return ret

# -*- coding: utf-8 -*-
'''
Return data to the host operating system's syslog facility

To use the syslog returner, append '--return syslog' to the
salt command.

.. code-block:: bash

    salt '*' test.ping --return syslog

The following fields can be set in the minion conf file::

    syslog.level (optional, Default: LOG_INFO)
    syslog.facility (optional, Default: LOG_USER)
    syslog.tag (optional, Default: salt-minion)
    syslog.options (list, optional, Default: [])

Available levels, facilities, and options can be found in the
``syslog`` docs for your python version.

.. note::

    The default tag comes from ``sys.argv[0]`` which is
    usually "salt-minion" but could be different based on
    the specific environment.

Configuration example:

.. code-block:: yaml

    syslog.level: 'LOG_ERR'
    syslog.facility: 'LOG_DAEMON'
    syslog.tag: 'mysalt'
    syslog.options:
      - LOG_PID

Of course you can also nest the options:

.. code-block:: yaml

    syslog:
      level: 'LOG_ERR'
      facility: 'LOG_DAEMON'
      tag: 'mysalt'
      options:
        - LOG_PID

Alternative configuration values can be used by
prefacing the configuration. Any values not found
in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.syslog.level: 'LOG_WARN'
    alternative.syslog.facility: 'LOG_NEWS'

To use the alternative configuration, append
``--return_config alternative`` to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return syslog --return_config alternative

To override individual configuration items, append
--return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return syslog --return_kwargs '{"level": "LOG_DEBUG"}'

.. note::

    Syslog server implementations may have limits on the maximum
    record size received by the client. This may lead to job
    return data being truncated in the syslog server's logs. For
    example, for rsyslog on RHEL-based systems, the default
    maximum record size is approximately 2KB (which return data
    can easily exceed). This is configurable in rsyslog.conf via
    the $MaxMessageSize config parameter. Please consult your syslog
    implmentation's documentation to determine how to adjust this limit.

'''
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import python libs
try:
    import syslog
    HAS_SYSLOG = True
except ImportError:
    HAS_SYSLOG = False

# Import Salt libs
import salt.utils.jid
import salt.utils.json
import salt.returners
from salt.ext import six

log = logging.getLogger(__name__)
# Define the module's virtual name
__virtualname__ = 'syslog'


def _get_options(ret=None):
    '''
    Get the returner options from salt.
    '''

    defaults = {'level': 'LOG_INFO',
                'facility': 'LOG_USER',
                'options': []
                }

    attrs = {'level': 'level',
             'facility': 'facility',
             'tag': 'tag',
             'options': 'options'
             }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__,
                                                   defaults=defaults)
    return _options


def _verify_options(options):
    '''
    Verify options and log warnings

    Returns True if all options can be verified,
    otherwise False
    '''

    # sanity check all vals used for bitwise operations later
    bitwise_args = [('level', options['level']),
                    ('facility', options['facility'])
                    ]
    bitwise_args.extend([('option', x) for x in options['options']])

    for opt_name, opt in bitwise_args:
        if not hasattr(syslog, opt):
            log.error('syslog has no attribute %s', opt)
            return False
        if not isinstance(getattr(syslog, opt), int):
            log.error('%s is not a valid syslog %s', opt, opt_name)
            return False

    # Sanity check tag
    if 'tag' in options:
        if not isinstance(options['tag'], six.string_types):
            log.error('tag must be a string')
            return False
        if len(options['tag']) > 32:
            log.error('tag size is limited to 32 characters')
            return False

    return True


def __virtual__():
    if not HAS_SYSLOG:
        return False, 'Could not import syslog returner; syslog is not installed.'
    return __virtualname__


def returner(ret):
    '''
    Return data to the local syslog
    '''

    _options = _get_options(ret)

    if not _verify_options(_options):
        return

    # Get values from syslog module
    level = getattr(syslog, _options['level'])
    facility = getattr(syslog, _options['facility'])

    # parse for syslog options
    logoption = 0
    for opt in _options['options']:
        logoption = logoption | getattr(syslog, opt)

    # Open syslog correctly based on options and tag
    try:
        if 'tag' in _options:
            syslog.openlog(ident=_options['tag'], logoption=logoption)
        else:
            syslog.openlog(logoption=logoption)
    except TypeError:
        # Python 2.6 syslog.openlog does not accept keyword args
        syslog.openlog(_options.get('tag', 'salt-minion'), logoption)

    # Send log of given level and facility
    syslog.syslog(facility | level, salt.utils.json.dumps(ret))

    # Close up to reset syslog to defaults
    syslog.closelog()


def prep_jid(nocache=False,
             passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)

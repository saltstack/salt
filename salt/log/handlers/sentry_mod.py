# -*- coding: utf-8 -*-
'''
    Sentry Logging Handler
    ======================

    .. versionadded:: 0.17.0

    This module provides a `Sentry`_ logging handler.

    .. admonition:: Note

        The `Raven`_ library needs to be installed on the system for this
        logging handler to be available.

    Configuring the python `Sentry`_ client, `Raven`_, should be done under the
    ``sentry_handler`` configuration key. Additional `context` may be provided
    for corresponding grain item(s).
    At the bare minimum, you need to define the `DSN`_. As an example:

    .. code-block:: yaml

        sentry_handler:
          dsn: https://pub-key:secret-key@app.getsentry.com/app-id


    More complex configurations can be achieved, for example:

    .. code-block:: yaml

        sentry_handler:
          servers:
            - https://sentry.example.com
            - http://192.168.1.1
          project: app-id
          public_key: deadbeefdeadbeefdeadbeefdeadbeef
          secret_key: beefdeadbeefdeadbeefdeadbeefdead
          context:
            - os
            - master
            - saltversion
            - cpuarch
            - ec2.tags.environment

    All the client configuration keys are supported, please see the
    `Raven client documentation`_.

    The default logging level for the sentry handler is ``ERROR``. If you wish
    to define a different one, define ``log_level`` under the
    ``sentry_handler`` configuration key:

    .. code-block:: yaml

      sentry_handler:
        dsn: https://pub-key:secret-key@app.getsentry.com/app-id
        log_level: warning


    The available log levels are those also available for the salt ``cli``
    tools and configuration; ``salt --help`` should give you the required
    information.


    Threaded Transports
    -------------------

    Raven's documents rightly suggest using its threaded transport for
    critical applications. However, don't forget that if you start having
    troubles with Salt after enabling the threaded transport, please try
    switching to a non-threaded transport to see if that fixes your problem.



    .. _`DSN`: https://raven.readthedocs.io/en/latest/config/index.html#the-sentry-dsn
    .. _`Sentry`: https://getsentry.com
    .. _`Raven`: https://raven.readthedocs.io
    .. _`Raven client documentation`: https://raven.readthedocs.io/en/latest/config/index.html#client-arguments
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.loader
from salt.log import LOG_LEVELS

# Import 3rd party libs
try:
    import raven
    from raven.handlers.logging import SentryHandler
    HAS_RAVEN = True
except ImportError:
    HAS_RAVEN = False

log = logging.getLogger(__name__)
__grains__ = {}
__salt__ = {}

# Define the module's virtual name
__virtualname__ = 'sentry'


def __virtual__():
    if HAS_RAVEN is True:
        __grains__ = salt.loader.grains(__opts__)
        __salt__ = salt.loader.minion_mods(__opts__)
        return __virtualname__
    return False


def setup_handlers():
    if 'sentry_handler' not in __opts__:
        log.debug('No \'sentry_handler\' key was found in the configuration')
        return False
    options = {}
    dsn = get_config_value('dsn')
    if dsn is not None:
        try:
            # support raven ver 5.5.0
            from raven.transport import TransportRegistry, default_transports
            from raven.utils.urlparse import urlparse
            transport_registry = TransportRegistry(default_transports)
            url = urlparse(dsn)
            if not transport_registry.supported_scheme(url.scheme):
                raise ValueError('Unsupported Sentry DSN scheme: {0}'.format(url.scheme))
        except ValueError as exc:
            log.info(
                'Raven failed to parse the configuration provided DSN: %s', exc
            )

    if not dsn:
        for key in ('project', 'servers', 'public_key', 'secret_key'):
            config_value = get_config_value(key)
            if config_value is None and key not in options:
                log.debug(
                    'The required \'sentry_handler\' configuration key, '
                    '\'%s\', is not properly configured. Not configuring '
                    'the sentry logging handler.', key
                )
                return
            elif config_value is None:
                continue
            options[key] = config_value

    # site: An optional, arbitrary string to identify this client installation.
    options.update({
        # site: An optional, arbitrary string to identify this client
        # installation
        'site': get_config_value('site'),

        # name: This will override the server_name value for this installation.
        # Defaults to socket.gethostname()
        'name': get_config_value('name'),

        # exclude_paths: Extending this allow you to ignore module prefixes
        # when sentry attempts to discover which function an error comes from
        'exclude_paths': get_config_value('exclude_paths', ()),

        # include_paths: For example, in Django this defaults to your list of
        # INSTALLED_APPS, and is used for drilling down where an exception is
        # located
        'include_paths': get_config_value('include_paths', ()),

        # list_max_length: The maximum number of items a list-like container
        # should store.
        'list_max_length': get_config_value('list_max_length'),

        # string_max_length: The maximum characters of a string that should be
        # stored.
        'string_max_length': get_config_value('string_max_length'),

        # auto_log_stacks: Should Raven automatically log frame stacks
        # (including locals) all calls as it would for exceptions.
        'auto_log_stacks': get_config_value('auto_log_stacks'),

        # timeout: If supported, the timeout value for sending messages to
        # remote.
        'timeout': get_config_value('timeout', 1),

        # processors: A list of processors to apply to events before sending
        # them to the Sentry server. Useful for sending additional global state
        # data or sanitizing data that you want to keep off of the server.
        'processors': get_config_value('processors'),

        # dsn: Ensure the DSN is passed into the client
        'dsn': dsn
    })

    client = raven.Client(**options)
    context = get_config_value('context')
    context_dict = {}
    if context is not None:
        for tag in context:
            tag_value = __salt__['grains.get'](tag)
            if len(tag_value) > 0:
                context_dict[tag] = tag_value
        if len(context_dict) > 0:
            client.context.merge({'tags': context_dict})
    try:
        handler = SentryHandler(client)
        handler.setLevel(LOG_LEVELS[get_config_value('log_level', 'error')])
        return handler
    except ValueError as exc:
        log.debug('Failed to setup the sentry logging handler', exc_info=True)


def get_config_value(name, default=None):
    return __opts__['sentry_handler'].get(name, default)

# encoding: utf-8

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import hashlib
import logging
import os

# Import salt libs
import salt.auth
from salt.utils.versions import StrictVersion as _StrictVersion

__virtualname__ = os.path.abspath(__file__).rsplit(os.sep)[-2] or 'rest_tornado'

log = logging.getLogger(__virtualname__)

# we require at least 4.0, as that includes all the Future's stuff we use
min_tornado_version = '4.0'
has_tornado = False
try:
    import tornado
    if _StrictVersion(tornado.version) >= _StrictVersion(min_tornado_version):
        has_tornado = True
    else:
        log.error('rest_tornado requires at least tornado %s', min_tornado_version)
except (ImportError, TypeError) as err:
    has_tornado = False
    log.error('ImportError! %s', err)


def __virtual__():
    mod_opts = __opts__.get(__virtualname__, {})

    if has_tornado and 'port' in mod_opts:
        return __virtualname__

    return False


def get_application(opts):
    try:
        from . import saltnado
    except ImportError as err:
        log.error('ImportError! %s', err)
        return None

    mod_opts = opts.get(__virtualname__, {})

    paths = [
        (r"/", saltnado.SaltAPIHandler),
        (r"/login", saltnado.SaltAuthHandler),
        (r"/minions/(.*)", saltnado.MinionSaltAPIHandler),
        (r"/minions", saltnado.MinionSaltAPIHandler),
        (r"/jobs/(.*)", saltnado.JobsSaltAPIHandler),
        (r"/jobs", saltnado.JobsSaltAPIHandler),
        (r"/run", saltnado.RunSaltAPIHandler),
        (r"/events", saltnado.EventsSaltAPIHandler),
        (r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
    ]

    # if you have enabled websockets, add them!
    if mod_opts.get('websockets', False):
        from . import saltnado_websockets

        token_pattern = r"([0-9A-Fa-f]{{{0}}})".format(len(getattr(hashlib, opts.get('hash_type', 'md5'))().hexdigest()))
        all_events_pattern = r"/all_events/{0}".format(token_pattern)
        formatted_events_pattern = r"/formatted_events/{0}".format(token_pattern)
        log.debug("All events URL pattern is %s", all_events_pattern)
        paths += [
            # Matches /all_events/[0-9A-Fa-f]{n}
            # Where n is the length of hexdigest
            # for the current hashing algorithm.
            # This algorithm is specified in the
            # salt master config file.
            (all_events_pattern, saltnado_websockets.AllEventsHandler),
            (formatted_events_pattern, saltnado_websockets.FormattedEventsHandler),
        ]

    application = tornado.web.Application(paths, debug=mod_opts.get('debug', False))

    application.opts = opts
    application.mod_opts = mod_opts
    application.auth = salt.auth.LoadAuth(opts)
    return application


def start():
    '''
    Start the saltnado!
    '''
    mod_opts = __opts__.get(__virtualname__, {})

    if 'num_processes' not in mod_opts:
        mod_opts['num_processes'] = 1

    if mod_opts['num_processes'] > 1 and mod_opts.get('debug', False) is True:
        raise Exception((
            'Tornado\'s debug implementation is not compatible with multiprocess. '
            'Either disable debug, or set num_processes to 1.'
        ))

    # the kwargs for the HTTPServer
    kwargs = {}
    if not mod_opts.get('disable_ssl', False):
        if 'ssl_crt' not in mod_opts:
            log.error("Not starting '%s'. Options 'ssl_crt' and "
                    "'ssl_key' are required if SSL is not disabled.",
                    __name__)

            return None
        # cert is required, key may be optional
        # https://docs.python.org/2/library/ssl.html#ssl.wrap_socket
        ssl_opts = {'certfile': mod_opts['ssl_crt']}
        if mod_opts.get('ssl_key', False):
            ssl_opts.update({'keyfile': mod_opts['ssl_key']})
        kwargs['ssl_options'] = ssl_opts

    import tornado.httpserver
    http_server = tornado.httpserver.HTTPServer(get_application(__opts__), **kwargs)
    try:
        http_server.bind(mod_opts['port'],
                         address=mod_opts.get('address'),
                         backlog=mod_opts.get('backlog', 128),
                         )
        http_server.start(mod_opts['num_processes'])
    except:
        log.error('Rest_tornado unable to bind to port %s', mod_opts['port'], exc_info=True)
        raise SystemExit(1)

    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        raise SystemExit(0)

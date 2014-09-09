# encoding: utf-8
import hashlib
import logging

__virtualname__ = 'rest_tornado'

logger = logging.getLogger(__virtualname__)

try:
    import tornado.httpserver
    import tornado.ioloop
    import tornado.web
    import tornado.gen

    has_tornado = True
except ImportError as err:
    has_tornado = False
    logger.info('ImportError! {0}'.format(str(err)))

import salt.auth


def __virtual__():
    mod_opts = __opts__.get(__virtualname__, {})

    if has_tornado and 'port' in mod_opts:
        return __virtualname__

    return False


def start():
    '''
    Start the saltnado!
    '''
    from . import saltnado

    mod_opts = __opts__.get(__virtualname__, {})

    if mod_opts.get('websockets', False):
        from . import saltnado_websockets

    if 'num_processes' not in mod_opts:
        mod_opts['num_processes'] = 1

    token_pattern = r"([0-9A-Fa-f]{0})".format(len(getattr(hashlib, __opts__.get('hash_type', 'md5'))().hexdigest()))

    all_events_pattern = r"/all_events/{0}".format(token_pattern)
    formatted_events_pattern = r"/formatted_events/{0}".format(token_pattern)
    logger.debug("All events URL pattern is {0}".format(all_events_pattern))

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

    application.opts = __opts__
    application.mod_opts = mod_opts
    application.auth = salt.auth.LoadAuth(__opts__)
    application.event_listener = saltnado.EventListener(mod_opts, __opts__)

    # the kwargs for the HTTPServer
    kwargs = {}
    if not mod_opts.get('disable_ssl', False):
        if 'ssl_crt' not in mod_opts:
            logger.error("Not starting '%s'. Options 'ssl_crt' and "
                    "'ssl_key' are required if SSL is not disabled.",
                    __name__)

            return None
        # cert is required, key may be optional
        # https://docs.python.org/2/library/ssl.html#ssl.wrap_socket
        ssl_opts = {'certfile': mod_opts['ssl_crt']}
        if mod_opts.get('ssl_key', False):
            ssl_opts.update({'keyfile': mod_opts['ssl_key']})
        kwargs['ssl_options'] = ssl_opts

    http_server = tornado.httpserver.HTTPServer(application, **kwargs)
    try:
        http_server.bind(mod_opts['port'])
        http_server.start(mod_opts['num_processes'])
    except:
        print 'Rest_tornado unable to bind to port {0}'.format(mod_opts['port'])
        raise SystemExit(1)
    tornado.ioloop.IOLoop.instance().add_callback(application.event_listener.iter_events)

    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        raise SystemExit(0)

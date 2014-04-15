import logging

try:
    import tornado.httpserver
    import tornado.ioloop
    import tornado.web
    import tornado.gen

    has_tornado = True
except ImportError:
    has_tornado = False

import salt.auth


__virtualname__ = 'rest_tornado'

logger = logging.getLogger(__virtualname__)


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

    if 'num_processes' not in mod_opts:
        mod_opts['num_processes'] = 1

    application = tornado.web.Application([
        (r"/", saltnado.SaltAPIHandler),
        (r"/login", saltnado.SaltAuthHandler),
        (r"/minions/(.*)", saltnado.MinionSaltAPIHandler),
        (r"/minions", saltnado.MinionSaltAPIHandler),
        (r"/jobs/(.*)", saltnado.JobsSaltAPIHandler),
        (r"/jobs", saltnado.JobsSaltAPIHandler),
        (r"/run", saltnado.RunSaltAPIHandler),
        (r"/events", saltnado.EventsSaltAPIHandler),
        (r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),

    ], debug=mod_opts.get('debug', False))

    application.opts = __opts__
    application.mod_opts = mod_opts
    application.auth = salt.auth.LoadAuth(__opts__)
    application.event_listener = saltnado.EventListener(mod_opts, __opts__)

    # the kwargs for the HTTPServer
    kwargs = {}
    if not mod_opts.get('disable_ssl', False):
        if 'certfile' not in mod_opts or 'keyfile' not in mod_opts:
            logger.error("Not starting '%s'. Options 'ssl_crt' and "
                    "'ssl_key' are required if SSL is not disabled.",
                    __name__)

            return None
        kwargs['ssl_options'] = {'certfile': mod_opts['ssl_crt'],
                                 'keyfile': mod_opts['ssl_key']}

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

'''
A REST interface for Salt using the CherryPy framework
'''
# Import Python libs
import itertools
import signal
import os

# Import third-party libs
import cherrypy
import cherrypy.wsgiserver as wsgiserver
import cherrypy.wsgiserver.ssl_builtin

# Import Salt libs
import salt.auth
import salt.log
import salt.output

# Import salt-api libs
import saltapi

logger = salt.log.logging.getLogger(__name__)

def __virtual__():
    return 'rest'

def salt_auth_tool(default=False):
    ignore_urls = ('/login',)
    sid = (cherrypy.session.get('token', None) or
            cherrypy.request.headers.get('X-Auth-Token', None))
    if not cherrypy.request.path_info in ignore_urls and not sid :
        raise cherrypy.InternalRedirect('/login')

cherrypy.tools.salt_auth = cherrypy.Tool('before_request_body', salt_auth_tool)

class LowDataAdapter(object):
    '''
    '''
    exposed = True

    def __init__(self, opts):
        self.opts = opts
        self.api = saltapi.APIClient(opts)

    def fmt_lowdata(self, data):
        '''
        Take CherryPy body data from a POST (et al) request and format it into
        lowdata. It will accept repeated parameters and pair and format those
        into multiple lowdata chunks.
        '''
        pairs = []
        for k,v in data.items():
            # Ensure parameter is a list
            argl = v if isinstance(v, list) else [v]
            # Make pairs of (key, value) from {key: [*value]}
            pairs.append(zip([k] * len(argl), argl))

        lowdata = []
        for i in itertools.izip_longest(*pairs):
            if not all(i):
                msg = "Error pairing parameters: %s"
                raise Exception(msg % str(i))
            lowdata.append(dict(i))

        return lowdata

    def exec_lowdata(self, lowdata):
        '''
        Pass lowdata to Salt to be executed
        '''
        # FIXME: change this to yield results from one of Salt's iterative returns
        logger.debug("SaltAPI is passing low-data: %s", lowdata)
        return [self.api.run(chunk) for chunk in lowdata]

    @cherrypy.tools.json_out()
    def GET(self):
        lowdata = [{'client': 'local', 'tgt': '*',
                'fun': ['grains.items', 'sys.list_functions'],
                'arg': [[], []],
        }]
        return self.exec_lowdata(lowdata)

    @cherrypy.tools.json_out()
    def POST(self, **kwargs):
        '''
        Run a given function in a given client with the given args
        '''
        return self.exec_lowdata(self.fmt_lowdata(kwargs))

class Login(LowDataAdapter):
    '''
    '''
    exposed = True

    def GET(self):
        cherrypy.response.status = '401 Unauthorized'
        cherrypy.response.headers['WWW-Authenticate'] = 'HTML'

        return '''\
            <html>
                <head>
                    <title>{status} - {message}</title>
                </head>
                <body>
                    <h1>{status}</h1>
                    <p>{message}</p>
                    <form method="post" action="/login">
                        <p>
                            <label for="username">Username:</label>
                            <input type="text" name="username">
                            <br>
                            <label for="password">Password:</label>
                            <input type="password" name="password">
                            <br>
                            <label for="eauth">Eauth:</label>
                            <input type="text" name="eauth" value="pam">
                        </p>
                        <p>
                            <button type="submit">Log in</button>
                        </p>
                    </form>
                </body>
            </html>'''.format(
                    status=cherrypy.response.status,
                    message="Please log in")

    def POST(self, **kwargs):
        auth = salt.auth.LoadAuth(self.opts)
        token = auth.mk_token(kwargs).get('token', False)
        cherrypy.response.headers['X-Auth-Token'] = cherrypy.session.id
        cherrypy.session['token'] = token
        raise cherrypy.HTTPRedirect('/', 302)

def error_page_default():
    cherrypy.response.status = 500
    ret = {
            'success': False,
            'message': '{0}'.format(cherrypy._cperror.format_exc())}
    cherrypy.response.body = [salt.output.out_format(ret, 'json_out', __opts__)]

def json_out_handler(*args, **kwargs):
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return salt.output.out_format(value, 'json_out', __opts__)

class API(object):
    url_map = {
        'index': LowDataAdapter,
        'login': Login,
    }

    def __init__(self, opts):
        self.opts = opts
        for url, cls in self.url_map.items():
            setattr(self, url, cls(self.opts))

    def verify_certs(self, *args):
        msg = ("Could not find a certificate: {0}\n"
                "If you want to quickly generate a self-signed certificate, "
                "use the tls.create_self_signed_cert function in Salt")

        for arg in args:
            if not os.path.exists(arg):
                raise Exception(msg.format(arg))

    def get_conf(self):
        # Grab config opts
        apiopts = self.opts.get('saltapi', {}).get(__name__.rsplit('.', 1)[-1], {})

        conf = {
            'global': {
                'server.socket_host': '0.0.0.0',
                'server.socket_port': apiopts.pop('port', 8000),
                'debug': apiopts.pop('debug', False),
            },
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'request.error_response': error_page_default,

                # 'response.stream': True,

                'tools.trailing_slash.on': True,
                'tools.json_out.handler': json_out_handler,

                'tools.sessions.on': True,
                'tools.sessions.timeout': 60 * 10, # 10 hours

                'tools.salt_auth.on': True,
            },
        }

        conf['global'].update(apiopts)
        return conf

def start():
    '''
    Server loop here. Started in a multiprocess.
    '''
    root = API(__opts__)
    conf = root.get_conf()
    gconf = conf.get('global', {})

    if gconf.get('debug', False):
        cherrypy.quickstart(root, '/', conf)
    else:
        root.verify_certs(gconf['ssl_crt'], gconf['ssl_key'])

        ssl_a = wsgiserver.ssl_builtin.BuiltinSSLAdapter(
                gconf['ssl_crt'], gconf['ssl_key'])
        wsgi_d = wsgiserver.WSGIPathInfoDispatcher({'/': root})
        server = wsgiserver.CherryPyWSGIServer(
                ('0.0.0.0', gconf['server.socket_port']),
                wsgi_app=wsgi_d,
                ssl_adapter=ssl_a)

        signal.signal(signal.SIGINT, lambda *args: server.stop())
        server.start()

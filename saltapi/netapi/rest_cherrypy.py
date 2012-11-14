'''
A hypermedia REST API for Salt using the CherryPy framework
'''
# Import Python libs
import itertools
import signal
import os
import json

# Import third-party libs
import cherrypy
import cherrypy.wsgiserver as wsgiserver
import cherrypy.wsgiserver.ssl_builtin

# Import Salt libs
import salt.auth
import salt.log
import salt.output
from salt.utils import yaml

# Import salt-api libs
import saltapi

logger = salt.log.logging.getLogger(__name__)

def __virtual__():
    if 'port' in __opts__.get(__name__.rsplit('.')[-1], {}):
        return 'rest'
    return False

def fmt_lowdata(data):
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

class SimpleTool(cherrypy.Tool):
    '''
    http://ionrock.org/better-cherrypy-tools.html
    '''
    def __init__(self, point=None, callable=None):
        self._point = point
        self._name = None
        self._priority = 50
        self._setargs()

    def _setup(self):
        conf = self._merged_args()
        hooks = cherrypy.request.hooks
        for hookpoint in cherrypy._cprequest.hookpoints:
            if hasattr(self, hookpoint):
                func = getattr(self, hookpoint)
                p = getattr(func, 'priority', self._priority)
                hooks.attach(hookpoint, func, priority=p, **conf)

def salt_auth_tool(default=False):
    ignore_urls = ('/login',)
    sid = (cherrypy.session.get('token', None) or
            cherrypy.request.headers.get('X-Auth-Token', None))
    if not cherrypy.request.path_info in ignore_urls and not sid :
        raise cherrypy.InternalRedirect('/login')

cherrypy.tools.salt_auth = cherrypy.Tool('before_request_body', salt_auth_tool)

class HypermediaTool(SimpleTool):
    '''
    A tool to set the in/out handler based on the Accept header
    '''
    ct_in_map = {
        'application/json': json.loads,
        'application/x-yaml': yaml.loads,
    }

    ct_out_map = {
        'application/json': 'json_out',
    }

    def before_handler(self, **conf):
        '''
        Unserialize POST/PUT data of a specified content type, if possible
        '''
        if cherrypy.request.method in ("POST", "PUT"):
            ct_type = cherrypy.request.headers['content-type'].lower()
            ct_in = self.ct_in_map.get(ct_type, None)

            if not ct_in:
                raise cherrypy.HTTPError(406, 'Content type not supported')

            body = cherrypy.request.body.read()
            cherrypy.request.params['body'] = ct_in(body)

    def before_finalize(self, *args, **kwargs):
        '''
        Run the return data from the handler through a Salt outputter then
        return the reponse
        '''
        accepts = cherrypy.request.headers.elements('Accept')
        for content_type in accepts:
            out = self.ct_out_map.get(content_type, None)

            if not out:
                raise cherrypy.HTTPError(406, 'Accept format not supported')

        ret = cherrypy.serving.request.handler(*args, **kwargs)
        cherrypy.response.body = salt.output.out_format(ret, out, __opts__)
        cherrypy.response.headers['Content-Type'] = content_type

    before_finalize.priority = 70 # late
    callable = before_finalize

cherrypy.tools.hypermedia_handler = HypermediaTool()

class LowDataAdapter(object):
    '''
    '''
    exposed = True

    def __init__(self, opts):
        self.opts = opts
        self.api = saltapi.APIClient(opts)

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

@cherrypy.tools.hypermedia_handler()
def error_page_default():
    cherrypy.response.status = 500
    ret = {
            'success': False,
            'message': '{0}'.format(cherrypy._cperror.format_exc())}
    cherrypy.response.body = [salt.output.out_format(ret, 'json_out', __opts__)]

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
        apiopts = self.opts.get(__name__.rsplit('.', 1)[-1], {})

        conf = {
            'global': {
                'server.socket_host': '0.0.0.0',
                'server.socket_port': apiopts.pop('port', 8000),
                'debug': apiopts.pop('debug', False),
            },
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'request.error_response': error_page_default,

                'tools.trailing_slash.on': True,

                'tools.sessions.on': True,
                'tools.sessions.timeout': 60 * 10, # 10 hours

                'tools.salt_auth.on': True,
                'tools.hypermedia_handler.on': True,
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

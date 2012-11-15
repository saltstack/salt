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

import jinja2

# Import Salt libs
import salt.auth
import salt.log
import salt.output
from salt.utils import yaml

# Import salt-api libs
import saltapi

logger = salt.log.logging.getLogger(__name__)

jenv = jinja2.Environment(loader=jinja2.FileSystemLoader([
    os.path.join(os.path.dirname(__file__), 'tmpl'),
]))

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

def salt_auth_tool():
    ignore_urls = ('/login',)

    # Grab the session via a cookie (for browsers) or via a custom header
    sid = (cherrypy.session.get('token', None) or
            cherrypy.request.headers.get('X-Auth-Token', None))

    if not cherrypy.request.path_info in ignore_urls and not sid :
        raise cherrypy.InternalRedirect('/login')

    cherrypy.response.headers['Cache-Control'] = 'private'

cherrypy.tools.salt_auth = cherrypy.Tool('before_request_body', salt_auth_tool)

# Be conservative in what you send
ct_out_map = {
    'application/json': 'json',
    'application/x-yaml': 'yaml',
    'text/html': 'jinja',
}

def hypermedia_handler(*args, **kwargs):
    best = cherrypy.lib.cptools.accept(ct_out_map.keys()) # raises 406
    out = ct_out_map[best]

    cherrypy.response.headers['Content-Type'] = best

    try:
        ret = cherrypy.serving.request._hypermedia_inner_handler(*args, **kwargs)
    except cherrypy.CherryPyException:
        raise
    except Exception as exc:
        logger.debug("Error while processing request for: %s",
                cherrypy.request.path_info,
                exc_info=True)

        cherrypy.response.status = 500
        cherrypy.response._tmpl = '500.html'

        ret = {
            'success': False,
            'status': cherrypy.response.status,
            'message': '{0}'.format(cherrypy._cperror.format_exc())}

    # Skip the outputters and use jinja instead
    if out == 'jinja':
        tmpl = jenv.get_template(cherrypy.response._tmpl)
        return tmpl.render(**ret)

    return salt.output.out_format(ret, out, __opts__)

def hypermedia_out():
    request = cherrypy.serving.request
    request._hypermedia_inner_handler = request.handler
    request.handler = hypermedia_handler

    # cherrypy.response.headers['Alternates'] = self.ct_out_map.keys()
    # TODO: add 'negotiate' to Vary header and 'list' to TCN header
    # Alternates: {"paper.1" 0.9 {type text/html} {language en}},
    #          {"paper.2" 0.7 {type text/html} {language fr}},
    #          {"paper.3" 1.0 {type application/postscript} {language en}}

cherrypy.tools.hypermedia_out = cherrypy.Tool('before_handler', hypermedia_out)

# Be liberal in what you accept
ct_in_map = {
    'application/x-www-form-urlencoded': fmt_lowdata,
    'application/json': json.loads,
    'application/x-yaml': yaml.load,
    'text/yaml': yaml.load,
}

def hypermedia_in():
    '''
    Unserialize POST/PUT data of a specified content type, if possible
    '''
    if cherrypy.request.method in ('POST', 'PUT'):
        ct_type = cherrypy.request.headers['content-type'].lower()
        ct_in = ct_in_map.get(ct_type, None)

        if not ct_in:
            raise cherrypy.HTTPError(406, 'Content type not supported')

        body = cherrypy.request.body.read()
        cherrypy.request.params['body'] = ct_in(body)

cherrypy.tools.hypermedia_in = cherrypy.Tool('before_handler', hypermedia_in)

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

    def GET(self):
        lowdata = [{'client': 'local', 'tgt': '*',
                'fun': ['grains.items', 'sys.list_functions'],
                'arg': [[], []],
        }]
        return self.exec_lowdata(lowdata)

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
        cherrypy.response._tmpl = 'login.html'
        cherrypy.response.status = '401 Unauthorized'
        cherrypy.response.headers['WWW-Authenticate'] = 'Session'

        return {
            'success': False,
            'status': cherrypy.response.status,
            'message': "Please log in",
        }

    def POST(self, **kwargs):
        auth = salt.auth.LoadAuth(self.opts)
        token = auth.mk_token(kwargs).get('token', False)
        cherrypy.response.headers['X-Auth-Token'] = cherrypy.session.id
        cherrypy.session['token'] = token
        raise cherrypy.HTTPRedirect('/', 302)

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

                'tools.trailing_slash.on': True,
                'tools.gzip.on': True,

                'tools.sessions.on': True,
                'tools.sessions.timeout': 60 * 10, # 10 hours
                'tools.salt_auth.on': True,

                # 'tools.autovary.on': True,
                'tools.hypermedia_out.on': True,
                'tools.hypermedia_in.on': True,
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

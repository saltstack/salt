'''
A REST interface for Salt using the CherryPy framework
'''
# Import Python libs
import itertools
import os

# Import third-party libs
import cherrypy
import cherrypy.wsgiserver as wsgiserver
import cherrypy.wsgiserver.ssl_builtin

# Import Salt libs
import salt.auth
import salt.log
import salt.output
from salt._compat import string_types

# Import salt-api libs
import saltapi

logger = salt.log.logging.getLogger(__name__)

def __virtual__():
    return 'rest'

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

    @cherrypy.tools.json_out()
    def POST(self, **kwargs):
        '''
        Run a given function in a given client with the given args
        '''
        lowdata = self.fmt_lowdata(kwargs)
        logger.debug("SaltAPI is passing LowData: %s", lowdata)

        return [self.api.run(chunk) for chunk in lowdata]

class Login(LowDataAdapter):
    '''
    '''
    exposed = True

    def POST(self, **kwargs):
        auth = salt.auth.LoadAuth(self.opts)
        token = auth.mk_token(self.fmt_lowdata(kwargs)).get('token', False)

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
        apiopts = self.opts.get('saltapi', {}).get(__name__.rsplit('.', 1)[-1], {})

        # ssl_crt = apiopts.get('ssl_crt', '')
        # ssl_key = apiopts.get('ssl_key', '')
        # verify_certs(ssl_crt, ssl_key)

        conf = {
            'global': {
                'server.socket_host': '0.0.0.0',
                'server.socket_port': apiopts.pop('port', 8000),
                'debug': apiopts.pop('debug', False),
            },
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'tools.trailing_slash.on': True,
                'request.error_response': error_page_default,
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

    if conf.get('global', {}).get('debug', False):
        cherrypy.quickstart(root, '/', conf)
    else:
        ssl_a = wsgiserver.ssl_builtin.BuiltinSSLAdapter(ssl_crt, ssl_key)
        wsgi_d = wsgiserver.WSGIPathInfoDispatcher({'/': app})
        server = wsgiserver.CherryPyWSGIServer(('0.0.0.0', port),
                wsgi_app=wsgi_d,
                ssl_adapter=ssl_a)

        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()

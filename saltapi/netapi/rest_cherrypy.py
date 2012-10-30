'''
A REST interface for Salt using the CherryPy framework
'''
# Import Python libs
import itertools
import os

# Import third-party libs
import cherrypy
import cheroot.wsgi
import cheroot.ssllib.ssl_builtin

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

    def get_lowdata(self):
        args = [zip(
            [k for i in range(len(v))], [v] if isinstance(v, string_types) else v)
            for k,v in cherrypy.request.body.params.items()]

        try:
            return [dict(i) for i in itertools.izip_longest(*args)]
        except TypeError as exc:
            msg = "Error trying to pair parameters in: %s"
            logger.debug(msg, args, exc_info=exc)
            raise Exception(msg % args)

    def POST(self, **kwargs):
        '''
        Run a given function in a given client with the given args
        '''
        lowdata = self.get_lowdata()
        logger.debug("SaltAPI is passing LowData: %s", lowdata)

        # lowvals = itertools.izip_longest(*[i[1] for i in cherrypy.request.body.read()])
        # lowdata = [dict(zip(cherrypy.request.body.read.keys(), i)) for i in lowvals]
        # ret = [self.api.run(chunk) for chunk in lowdata]
        # json_ret = salt.output.display_output(ret, 'json_out', __opts__)

class Login(LowDataAdapter):
    '''
    '''
    exposed = True

    def POST(self, **kwargs):
        auth = salt.auth.LoadAuth(self.opts)
        token = auth.mk_token(self.get_lowdata()).get('token', False)

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
        ssl_a = cheroot.ssllib.ssl_builtin.BuiltinSSLAdapter(ssl_crt, ssl_key)
        wsgi_d = cheroot.wsgi.WSGIPathInfoDispatcher({'/': app})
        server = cheroot.wsgi.WSGIServer(('0.0.0.0', port),
                wsgi_app=wsgi_d,
                ssl_adapter=ssl_a)

        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()

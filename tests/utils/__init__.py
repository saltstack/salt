# coding: utf-8

try:
    import cherrypy
    HAS_CHERRYPY = True
except ImportError:
    HAS_CHERRYPY = False

import mock

if HAS_CHERRYPY:
    from . cptestcase import BaseCherryPyTestCase
    from salt.netapi.rest_cherrypy import app
else:
    from salttesting.unit import TestCase, skipIf

    @skipIf(HAS_CHERRYPY is False, 'The CherryPy python package needs to be installed')
    class BaseCherryPyTestCase(TestCase):
        pass

    class BaseToolsTest(BaseCherryPyTestCase):
        pass


class BaseRestCherryPyTest(BaseCherryPyTestCase):
    '''
    A base TestCase subclass for the rest_cherrypy module

    This mocks all interactions with Salt-core and sets up a dummy
    (unsubscribed) CherryPy web server.
    '''
    __opts__ = None

    @mock.patch('salt.netapi.NetapiClient', autospec=True)
    @mock.patch('salt.auth.Resolver', autospec=True)
    @mock.patch('salt.auth.LoadAuth', autospec=True)
    @mock.patch('salt.utils.event.get_event', autospec=True)
    def setUp(self, get_event, LoadAuth, Resolver, NetapiClient):  # pylint: disable=W0221
        app.salt.netapi.NetapiClient = NetapiClient
        app.salt.auth.Resolver = Resolver
        app.salt.auth.LoadAuth = LoadAuth
        app.salt.utils.event.get_event = get_event

        # Make local references to mocked objects so individual tests can
        # access and modify the mocked interfaces.
        self.Resolver = Resolver
        self.NetapiClient = NetapiClient
        self.get_event = get_event

        __opts__ = self.__opts__ or {
            'external_auth': {
                'auto': {
                    'saltdev': [
                        '@wheel',
                        '@runner',
                        '.*',
                    ],
                }
            },
            'rest_cherrypy': {
                'port': 8000,
                'debug': True,
            },
        }

        root, apiopts, conf = app.get_app(__opts__)

        cherrypy.tree.mount(root, '/', conf)
        cherrypy.server.unsubscribe()
        cherrypy.engine.start()

    def tearDown(self):
        cherrypy.engine.exit()


class Root(object):
    '''
    The simplest CherryPy app needed to test individual tools
    '''
    exposed = True

    _cp_config = {}

    def GET(self):
        return {'return': ['Hello world.']}

    def POST(self, *args, **kwargs):
        return {'return': [{'args': args}, {'kwargs': kwargs}]}


if HAS_CHERRYPY:
    class BaseToolsTest(BaseCherryPyTestCase):  # pylint: disable=E0102
        '''
        A base class so tests can selectively turn individual tools on for testing
        '''
        conf = {
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            },
        }

        def setUp(self):
            Root._cp_config = self._cp_config
            root = Root()

            cherrypy.tree.mount(root, '/', self.conf)
            cherrypy.server.unsubscribe()
            cherrypy.engine.start()

        def tearDown(self):
            cherrypy.engine.exit()

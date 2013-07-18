# coding: utf-8
import cherrypy
import mock

from saltapi.netapi.rest_cherrypy import app

from . cptestcase import BaseCherryPyTestCase

class BaseRestCherryPyTest(BaseCherryPyTestCase):
    '''
    A base TestCase subclass for the rest_cherrypy module

    This mocks all interactions with Salt-core and sets up a dummy
    (unsubscribed) CherryPy web server.
    '''
    @mock.patch('saltapi.APIClient', autospec=True)
    @mock.patch('salt.auth.Resolver', autospec=True)
    def setUp(self, Resolver, APIClient):
        app.saltapi.APIClient = APIClient
        app.salt.auth.Resolver = Resolver

        # Make local references to mocked objects so individual tests can
        # access and modify the mocked interfaces.
        self.Resolver = Resolver
        self.APIClient = APIClient

        __opts__ = {
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


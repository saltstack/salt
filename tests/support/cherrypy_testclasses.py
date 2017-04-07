# -*- coding: utf-8 -*-
from __future__ import absolute_import

try:
    import cherrypy

    HAS_CHERRYPY = True
except ImportError:
    HAS_CHERRYPY = False

import os

import salt.config
from tests.support.paths import TMP_CONF_DIR

if HAS_CHERRYPY:
    from tests.support.cptestcase import BaseCherryPyTestCase
    from salt.netapi.rest_cherrypy import app
else:
    from tests.support.unit import TestCase, skipIf

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

    @classmethod
    def setUpClass(cls):
        master_conf = os.path.join(TMP_CONF_DIR, 'master')
        cls.config = salt.config.client_config(master_conf)
        cls.base_opts = {}
        cls.base_opts.update(cls.config)

    @classmethod
    def tearDownClass(cls):
        del cls.config
        del cls.base_opts

    def setUp(self):
        # Make a local reference to the CherryPy app so we can mock attributes.
        self.app = app

        __opts__ = self.base_opts.copy()
        __opts__.update(self.__opts__ or {
            'external_auth': {
                'auto': {
                    'saltdev': [
                        '@wheel',
                        '@runner',
                        '.*',
                    ],
                 },
                 'pam': {
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
        })

        root, apiopts, conf = app.get_app(__opts__)

        cherrypy.tree.mount(root, '/', conf)
        cherrypy.server.unsubscribe()
        cherrypy.engine.start()

    def tearDown(self):
        cherrypy.engine.exit()
        del self.app


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
            if not hasattr(self, '_cp_config'):
                self._cp_config = {}
            Root._cp_config = self._cp_config
            root = Root()

            cherrypy.tree.mount(root, '/', self.conf)
            cherrypy.server.unsubscribe()
            cherrypy.engine.start()

        def tearDown(self):
            cherrypy.engine.exit()
            try:
                del self._cp_config
            except AttributeError:
                pass

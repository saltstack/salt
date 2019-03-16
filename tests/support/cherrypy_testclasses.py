# -*- coding: utf-8 -*-
from __future__ import absolute_import

try:
    import cherrypy
    HAS_CHERRYPY = True
except ImportError:
    HAS_CHERRYPY = False

import os

import salt.config
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS

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
    def __get_opts__(self):
        return None

    @classmethod
    def setUpClass(cls):
        master_conf = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master')
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
        self.addCleanup(delattr, self, 'app')

        master_conf = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master')
        client_config = salt.config.client_config(master_conf)
        base_opts = {}
        base_opts.update(client_config)

        base_opts.update(self.__get_opts__() or {
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

        root, apiopts, conf = app.get_app(base_opts)
        cherrypy.tree.mount(root, '/', conf)
        cherrypy.server.unsubscribe()
        cherrypy.engine.start()

        # Make sure cherrypy does not memleak on it's bus since it keeps
        # adding handlers without cleaning the old ones each time we setup
        # a new application
        for value in cherrypy.engine.listeners.values():
            value.clear()
        cherrypy.engine._priorities.clear()

        self.addCleanup(cherrypy.engine.exit)


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
        def __get_conf__(self):
            return {
                '/': {
                    'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                },
            }

        def __get_cp_config__(self):
            return {}

        def setUp(self):
            root = Root()
            patcher = patch.object(root, '_cp_config', self.__get_cp_config__())
            patcher.start()
            self.addCleanup(patcher.stop)

            # Make sure cherrypy does not memleak on it's bus since it keeps
            # adding handlers without cleaning the old ones each time we setup
            # a new application
            for value in cherrypy.engine.listeners.values():
                value.clear()
            cherrypy.engine._priorities.clear()

            app = cherrypy.tree.mount(root, '/', self.__get_conf__())
            cherrypy.server.unsubscribe()
            cherrypy.engine.start()
            self.addCleanup(cherrypy.engine.exit)

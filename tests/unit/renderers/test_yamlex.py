# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase

# Import Salt libs
import salt.state
from salt.config import minion_config
from salt.template import compile_template_str
import salt.serializers.yamlex as yamlex

basic_template = '''#!yamlex
foo: bar
'''

complex_template = '''#!yamlex
placeholder: {foo: !aggregate {foo: 42}}
placeholder: {foo: !aggregate {bar: null}}
placeholder: {foo: !aggregate {baz: inga}}
'''

SKIP_MESSAGE = '%s is unavailable, do prerequisites have been met?'


class RendererMixin(object):
    def render(self, template, opts=None):
        _config = minion_config(None)
        _config['file_client'] = 'local'
        if opts:
            _config.update(opts)
        _state = salt.state.State(_config)
        return compile_template_str(template,
                                    _state.rend,
                                    _state.opts['renderer'],
                                    _state.opts['renderer_blacklist'],
                                    _state.opts['renderer_whitelist'])


class RendererTests(TestCase, RendererMixin, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {yamlex: {}}

    @skipIf(not yamlex.available, SKIP_MESSAGE % 'yamlex')
    def test_basic(self):
        sls_obj = self.render(basic_template)
        assert sls_obj == {'foo': 'bar'}, sls_obj

    @skipIf(not yamlex.available, SKIP_MESSAGE % 'yamlex')
    def test_complex(self):

        sls_obj = self.render(complex_template)
        assert sls_obj == {
            'placeholder': {
                'foo': {
                    'foo': 42,
                    'bar': None,
                    'baz': 'inga'
                }
            }
        }, sls_obj

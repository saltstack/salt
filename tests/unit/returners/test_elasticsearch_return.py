# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import elasticsearch
from salt.returners import elasticsearch_return

# Import elasticsearch exceptions
NO_ELASTIC = False
try:
    from elasticsearch import NotFoundError
except Exception:
    NO_ELASTIC = True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(NO_ELASTIC, 'Install elasticsearch-py before running Elasticsearch unit tests.')
class ElasticsearchJobCacheTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Tests for the Elasticsearch Returner Job Cache
    '''
    def setup_loader_modules(self):
        module_globals = {
            elasticsearch_return: {
                '__salt__': {
                    'elasticsearch.document_get': elasticsearch.document_get
                }
            }
        }
        return module_globals

    def test_get_load(self):
        '''
        Test that we return a job when one is found
        '''
        class MockElastic(object):
            '''
            Mock of Elasticsearch client
            '''
            def get(self, index=None, doc_type=None, id=None):
                '''
                Mock of index method
                '''
                return {'_id': '20190626162818326147',
                        '_index': 'salt-master-job-cache-v1',
                        '_primary_term': 6,
                        '_seq_no': 22,
                        '_source': {'jid': '20190626162818326147',
                                    'load': {'arg': [],
                                             'cmd': 'publish',
                                             'fun': 'test.version',
                                             'jid': '20190626162818326147',
                                             'kwargs': {'delimiter': ':',
                                                        'show_jid': False,
                                                        'show_timeout': True},
                                             'ret': '',
                                             'tgt': '*',
                                             'tgt_type': 'glob',
                                             'user': 'test'}},
                        '_type': 'default',
                        '_version': 1,
                        'found': True}

        with patch.object(elasticsearch, '_get_instance',
                          MagicMock(return_value=MockElastic())):
            self.assertDictEqual(
                elasticsearch_return.get_load("20190626162818326147"),
                {'_id': '20190626162818326147',
                 '_index': 'salt-master-job-cache-v1',
                 '_primary_term': 6,
                 '_seq_no': 22,
                 '_source': {'jid': '20190626162818326147',
                             'load': {'arg': [],
                                      'cmd': 'publish',
                                      'fun': 'test.version',
                                      'jid': '20190626162818326147',
                                      'kwargs': {'delimiter': ':',
                                                 'show_jid': False,
                                                 'show_timeout': True},
                                      'ret': '',
                                      'tgt': '*',
                                      'tgt_type': 'glob',
                                      'user': 'test'}},
                 '_type': 'default',
                 '_version': 1,
                 'found': True}
            )

    def test_get_load_notfound(self):
        '''
        Tests that we return an empty dict when no job is found
        '''
        class MockElastic(object):
            '''
            Mock of Elasticsearch client
            '''
            def get(self, index=None, doc_type=None, id=None):
                '''
                Mock of index method
                '''
                raise NotFoundError

        with patch.object(elasticsearch, '_get_instance',
                          MagicMock(return_value=MockElastic())):
            self.assertDictEqual(elasticsearch_return.get_load("bogusjid"), {})

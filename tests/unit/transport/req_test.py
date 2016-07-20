# -*- coding: utf-8 -*-


class ReqChannelMixin(object):
    def test_basic(self):
        '''
        Test a variety of messages, make sure we get the expected responses
        '''
        msgs = [
            {'foo': 'bar'},
            {'bar': 'baz'},
            {'baz': 'qux', 'list': [1, 2, 3]},
        ]
        for msg in msgs:
            ret = self.channel.send(msg, timeout=2, tries=1)
            self.assertEqual(ret['load'], msg)

    def test_normalization(self):
        '''
        Since we use msgpack, we need to test that list types are converted to lists
        '''
        types = {
            'list': list,
        }
        msgs = [
            {'list': tuple([1, 2, 3])},
        ]
        for msg in msgs:
            ret = self.channel.send(msg, timeout=2, tries=1)
            for k, v in ret['load'].iteritems():
                self.assertEqual(types[k], type(v))

    def test_badload(self):
        '''
        Test a variety of bad requests, make sure that we get some sort of error
        '''
        msgs = ['', [], tuple()]
        for msg in msgs:
            ret = self.channel.send(msg, timeout=2, tries=1)
            self.assertEqual(ret, 'payload and load must be a dict')

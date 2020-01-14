# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

from tests.support.unit import skipIf

import salt.utils.platform
import salt.utils.files


class JinjaFiltersTest(object):
    '''
    testing Jinja filters are available via state system
    '''

    def test_data_compare_dicts(self):
        '''
        test jinja filter data.compare_dicts
        '''
        _expected = {'ret': {'a': {'new': 'c', 'old': 'b'}}}

        ret = self.run_function('state.sls',
                                ['jinja_filters.data_compare_dicts'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_compare_lists(self):
        '''
        test jinja filter data.compare_list
        '''
        _expected = {'ret': {'old': ['b']}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_compare_lists'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_decode_dict(self):
        '''
        test jinja filter data.decode_dict
        '''
        _expected = {'ret': {'a': 'b', 'c': 'd'}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_decode_dict'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_data_decode_list(self):
        '''
        test jinja filter data.decode_list
        '''
        _expected = {'ret': ['a', 'b', 'c', 'd']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_decode_list'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_data_encode_dict(self):
        '''
        test jinja filter data.encode_dict
        '''
        _expected = {'ret': {'a': 'b', 'c': 'd'}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_encode_dict'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_data_encode_list(self):
        '''
        test jinja filter data.encode_list
        '''
        _expected = {'ret': ['a', 'b', 'c', 'd']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_encode_list'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_data_exactly_n(self):
        '''
        test jinja filter data.exactly_n
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_exactly_n'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_exactly_one(self):
        '''
        test jinja filter data.exactly_one
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_exactly_one'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_is_iter(self):
        '''
        test jinja filter data.is_iter
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_is_iter'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_is_list(self):
        '''
        test jinja filter data.is_list
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_is_list'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_mysql_to_dict(self):
        '''
        test jinja filter data.mysql_to_dict
        '''
        _expected = {'ret': {'show processlist': {'Info': 'show processlist', 'db': 'NULL', 'Host': 'localhost', 'State': 'init', 'Command': 'Query', 'User': 'root', 'Time': 0, 'Id': 7}}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_mysql_to_dict'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_sorted_ignorecase(self):
        '''
        test jinja filter data.softed_ignorecase
        '''
        _expected = {'ret': ['Abcd', 'efgh', 'Ijk', 'lmno', 'Pqrs']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_sorted_ignorecase'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_data_substring_in_list(self):
        '''
        test jinja filter data.substring_in_list
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.data_substring_in_list'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_dateutils_strftime(self):
        '''
        test jinja filter datautils.strftime
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.dateutils_strftime'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_files_is_binary(self):
        '''
        test jinja filter files.is_binary
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.files_is_binary'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_files_is_empty(self):
        '''
        test jinja filter files.is_empty
        '''
        try:
            if salt.utils.platform.is_windows():
                with salt.utils.files.fopen('c:\\empty_file', 'w') as fp:
                    pass
            _expected = {'ret': True}
            ret = self.run_function('state.sls',
                                    ['jinja_filters.files_is_empty'])
            assert 'module_|-test_|-test.echo_|-run' in ret
            assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                             _expected
        finally:
            if salt.utils.platform.is_windows():
                os.remove('c:\\empty_file')

    def test_files_is_text(self):
        '''
        test jinja filter files.is_text
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.files_is_text'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_files_list_files(self):
        '''
        test jinja filter files.list_files
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.files_list_files'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        if salt.utils.platform.is_windows():
            assert 'c:\\\\salt\\\\conf\\\\minion' in \
                          ret['module_|-test_|-test.echo_|-run']['changes']['ret']
        else:
            assert '/bin/ls' in \
                          ret['module_|-test_|-test.echo_|-run']['changes']['ret']

    def test_hashutils_base4_64decode(self):
        '''
        test jinja filter hashutils.base64_64decode
        '''
        _expected = {'ret': 'Salt Rocks!'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_base4_64decode'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_hashutils_base4_64encode(self):
        '''
        test jinja filter hashutils.base64_64encode
        '''
        _expected = {'ret': 'U2FsdCBSb2NrcyE='}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_base4_64encode'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_hashutils_file_hashsum(self):
        '''
        test jinja filter hashutils.file_hashsum
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_file_hashsum'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_hashutils_hmac(self):
        '''
        test jinja filter hashutils.hmac
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_hmac'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_hashutils_md5_digest(self):
        '''
        test jinja filter hashutils.md5_digest
        '''
        _expected = {'ret': '85d6e71db655ee8e42c8b18475f0925f'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_md5_digest'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_hashutils_random_hash(self):
        '''
        test jinja filter hashutils.random_hash
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_random_hash'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in \
                      ret['module_|-test_|-test.echo_|-run']['changes']

    def test_hashutils_sha256_digest(self):
        '''
        test jinja filter hashutils.sha256_digest
        '''
        _expected = {'ret': 'cce7fe00fd9cc6122fd3b2ed22feae215bcfe7ac4a7879d336c1993426a763fe'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_sha256_digest'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_hashutils_sha512_digest(self):
        '''
        test jinja filter hashutils.sha512_digest
        '''
        _expected = {'ret': '44d829491d8caa7039ad08a5b7fa9dd0f930138c614411c5326dd4755fdc9877ec6148219fccbe404139e7bb850e77237429d64f560c204f3697ab489fd8bfa5'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.hashutils_sha512_digest'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_http_query(self):
        '''
        test jinja filter http.query
        '''
        _expected = {'ret': {}}
        ret = self.run_function('state.sls',
                                ['jinja_filters.http_query'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_avg(self):
        '''
        test jinja filter jinja.avg
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_avg'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_jinja_difference(self):
        '''
        test jinja filter jinja.difference
        '''
        _expected = {'ret': [1, 3]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_difference'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_intersect(self):
        '''
        test jinja filter jinja.intersect
        '''
        _expected = {'ret': [2, 4]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_intersect'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_max(self):
        '''
        test jinja filter jinja.max
        '''
        _expected = {'ret': 4}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_max'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_min(self):
        '''
        test jinja filter jinja.min
        '''
        _expected = {'ret': 1}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_min'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_quote(self):
        '''
        test jinja filter jinja.quote
        '''
        _expected = {'ret': 'Salt Rocks!'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_quote'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_regex_escape(self):
        '''
        test jinja filter jinja.regex_escape
        '''
        _expected = {'ret': 'Salt\\ Rocks'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_escape'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_regex_match(self):
        '''
        test jinja filter jinja.regex_match
        '''
        _expected = {'ret': "('a', 'd')"}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_match'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_regex_replace(self):
        '''
        test jinja filter jinja.regex_replace
        '''
        _expected = {'ret': 'lets__replace__spaces'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_replace'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_regex_search(self):
        '''
        test jinja filter jinja.regex_search
        '''
        _expected = {'ret': "('a', 'd')"}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_regex_search'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_sequence(self):
        '''
        test jinja filter jinja.sequence
        '''
        _expected = {'ret': ['Salt Rocks!']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_sequence'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_skip(self):
        '''
        test jinja filter jinja.skip
        '''
        _expected = {'ret': None}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_skip'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_symmetric_difference(self):
        '''
        test jinja filter jinja.symmetric_difference
        '''
        _expected = {'ret': [1, 3, 6]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_symmetric_difference'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_to_bool(self):
        '''
        test jinja filter jinja.to_bool
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_to_bool'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_union(self):
        '''
        test jinja filter jinja.union
        '''
        _expected = {'ret': [1, 2, 3, 4, 6]}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_union'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_unique(self):
        '''
        test jinja filter jinja.unique
        '''
        _expected = {'ret': ['a', 'b', 'c']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_unique'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_jinja_uuid(self):
        '''
        test jinja filter jinja.uuid
        '''
        _expected = {'ret': '799192d9-7f32-5227-a45f-dfeb4a34e06f'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.jinja_uuid'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_network_gen_mac(self):
        '''
        test jinja filter network.gen_mac
        '''
        _expected = 'AC:DE:48:'
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_gen_mac'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes']['ret'].startswith(_expected)

    def test_network_ipaddr(self):
        '''
        test jinja filter network.ipaddr
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ipaddr'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_network_ip_host(self):
        '''
        test jinja filter network.ip_host
        '''
        _expected = {'ret': '192.168.0.12/24'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ip_host'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_network_ipv4(self):
        '''
        test jinja filter network.ipv4
        '''
        _expected = {'ret': ['127.0.0.1']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ipv4'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_network_ipv6(self):
        '''
        test jinja filter network.ipv6
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_ipv6'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_network_is_ip(self):
        '''
        test jinja filter network.is_ip
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_is_ip'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_network_is_ipv4(self):
        '''
        test jinja filter network.is_ipv4
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_is_ipv4'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_network_is_ipv6(self):
        '''
        test jinja filter network.is_ipv6
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_is_ipv6'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_network_network_hosts(self):
        '''
        test jinja filter network.network_hosts
        '''
        _expected = {'ret': ['192.168.1.1', '192.168.1.2']}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_network_hosts'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_network_network_size(self):
        '''
        test jinja filter network.network_size
        '''
        _expected = {'ret': 16}
        ret = self.run_function('state.sls',
                                ['jinja_filters.network_network_size'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_path_join(self):
        '''
        test jinja filter path.join
        '''
        _expected = {'ret': os.path.sep + os.path.join('a', 'b', 'c', 'd')}
        ret = self.run_function('state.sls',
                                ['jinja_filters.path_join'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_path_which(self):
        '''
        test jinja filter path.which
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.path_which'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_stringutils_contains_whitespace(self):
        '''
        test jinja filter stringutils.contains_whitespace
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_contains_whitespace'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_stringutils_is_hex(self):
        '''
        test jinja filter stringutils.is_hex
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_is_hex'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_stringutils_random_str(self):
        '''
        test jinja filter stringutils.random_str
        '''
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_random_str'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_stringutils_to_bytes(self):
        '''
        test jinja filter stringutils.to_bytes
        '''
        _expected = {'ret': 'Salt Rocks!'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_to_bytes'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert 'ret' in ret['module_|-test_|-test.echo_|-run']['changes']

    def test_stringutils_to_num(self):
        '''
        test jinja filter stringutils.to_num
        '''
        _expected = {'ret': 42}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_to_num'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_stringutils_whitelist_blacklist(self):
        '''
        test jinja filter stringutils.whitelist_blacklist
        '''
        _expected = {'ret': True}
        ret = self.run_function('state.sls',
                                ['jinja_filters.stringutils_whitelist_blacklist'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    @skipIf(salt.utils.platform.is_windows(), 'Skip on windows')
    def test_user_get_uid(self):
        '''
        test jinja filter user.get_uid
        '''
        _expected = {'ret': 0}
        ret = self.run_function('state.sls',
                                ['jinja_filters.user_get_uid'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_yamlencoding_yaml_dquote(self):
        '''
        test jinja filter yamlencoding.yaml_dquote
        '''
        _expected = {'ret': 'A double-quoted string in YAML'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.yamlencoding_yaml_dquote'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_yamlencoding_yaml_encode(self):
        '''
        test jinja filter yamlencoding.yaml_encode
        '''
        _expected = {'ret': 'An encoded string in YAML'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.yamlencoding_yaml_encode'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_yamlencoding_yaml_squote(self):
        '''
        test jinja filter yamlencoding.yaml_squote
        '''
        _expected = {'ret': 'A single-quoted string in YAML'}
        ret = self.run_function('state.sls',
                                ['jinja_filters.yamlencoding_yaml_squote'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_yaml(self):
        '''
        test yaml filter
        '''
        _expected = {'ret': "{Question: 'Quieres Café?'}"}
        ret = self.run_function('state.sls', ['jinja_filters.yaml'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

    def test_json(self):
        '''
        test json filter
        '''
        _expected = {'ret': '{"Question": "Quieres Café?"}'}
        ret = self.run_function('state.sls', ['jinja_filters.json'])
        assert 'module_|-test_|-test.echo_|-run' in ret
        assert ret['module_|-test_|-test.echo_|-run']['changes'] == \
                         _expected

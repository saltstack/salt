"""
Testing Jinja filters availablilty via state system
"""
import logging
import os

import attr
import pytest

import salt.utils.files
import salt.utils.path

log = logging.getLogger(__name__)


@attr.s
class Filter:
    name = attr.ib()
    sls = attr.ib()
    expected = attr.ib(default=None)
    _exits = attr.ib(init=False, repr=False, factory=list)

    def check_skip(self, grains):
        pass

    def assert_result(self, changes):
        __tracebackhide__ = True
        assert changes
        if self.expected:
            if callable(self.expected):
                assert self.expected(changes)
            else:
                assert changes == self.expected

    def __call__(self, state_tree):
        self.state_tree = state_tree
        return self

    def __enter__(self):
        filter_sls = pytest.helpers.temp_file("filter.sls", self.sls, self.state_tree)
        filter_sls.__enter__()
        self._exits.append(filter_sls)
        return self

    def __exit__(self, *_):
        for exit_callback in self._exits:
            exit_callback.__exit__(*_)


@attr.s
class SkipOnWindowsFilter(Filter):
    def check_skip(self, grains):
        if grains["os"] == "Windows":
            pytest.skip("Skipped on windows")


@attr.s
class StartsWithFilter(Filter):
    def assert_result(self, changes):
        __tracebackhide__ = True
        assert changes
        assert changes["ret"]
        assert changes["ret"].startswith(self.expected)


@attr.s
class SortedFilter(Filter):
    def assert_result(self, changes):
        __tracebackhide__ = True
        assert changes
        assert changes["ret"]
        assert sorted(changes["ret"]) == sorted(self.expected["ret"])


@attr.s
class EmptyFileFilter(Filter):

    name = attr.ib(default="is_empty")
    sls = attr.ib(
        default="""
        {% set result = 'FPATH' | is_empty() %}
        test:
          module.run:
            - name: test.echo
            - text: {{ result }}
        """
    )

    def __enter__(self):
        empty_file = pytest.helpers.temp_file("empty-file", "", self.state_tree)
        fpath = empty_file.__enter__()
        self._exits.append(empty_file)
        self.sls = self.sls.replace("FPATH", str(fpath))
        return super().__enter__()


@attr.s
class TextFileFilter(Filter):

    name = attr.ib(default="is_text_file")
    sls = attr.ib(
        default="""
        {% set result = 'FPATH' | is_text_file() %}
        test:
          module.run:
            - name: test.echo
            - text: {{ result }}
        """
    )

    def __enter__(self):
        text_file = pytest.helpers.temp_file(
            "text-file", "This is a text file", self.state_tree
        )
        fpath = text_file.__enter__()
        self._exits.append(text_file)
        self.sls = self.sls.replace("FPATH", str(fpath))
        return super().__enter__()


@attr.s
class ListFilesFilter(SortedFilter):

    name = attr.ib(default="list_files")
    sls = attr.ib(
        default="""
        {% set result = 'FPATH' | list_files() %}
        test:
          module.run:
            - name: test.echo
            - text: {{ result }}
        """
    )

    def __enter__(self):
        text_file = pytest.helpers.temp_file(
            "foo/text-file", "This is a text file", self.state_tree
        )
        fpath = text_file.__enter__()
        self._exits.append(text_file)
        self.sls = self.sls.replace("FPATH", str(self.state_tree / "foo"))
        self.expected = {"ret": [str(self.state_tree / "foo"), str(fpath)]}
        return super().__enter__()


@attr.s
class FileHashsumFilter(Filter):

    name = attr.ib(default="file_hashsum")
    expected = attr.ib(
        default={
            "ret": "bfae4a86e38196ebccd4b9ef32454ff4271afa4ad539106de37d318591533873"
        }
    )
    sls = attr.ib(
        default="""
        {% set result = 'FPATH' | file_hashsum() %}
        test:
          module.run:
            - name: test.echo
            - text: {{ result }}
        """
    )

    def __enter__(self):
        text_file = pytest.helpers.temp_file(
            "text-file", "This is a text file", self.state_tree
        )
        fpath = text_file.__enter__()
        self._exits.append(text_file)
        self.sls = self.sls.replace("FPATH", str(fpath))
        return super().__enter__()


def _filter_id(value):
    return value.name


@pytest.fixture(
    params=[
        Filter(
            name="compare_dicts",
            expected={"ret": {"a": {"new": "c", "old": "b"}}},
            sls="""
            {% set dict_one = {'a': 'b', 'c': 'd'} %}
            {% set dict_two = {'a': 'c', 'c': 'd'} %}

            {% set result = dict_one | compare_dicts(dict_two) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result|tojson }}
            """,
        ),
        Filter(
            name="compare_lists",
            expected={"ret": {"old": ["b"]}},
            sls="""
            {% set list_one = ['a', 'b', 'c', 'd'] %}
            {% set list_two = ['a', 'c', 'd'] %}

            {% set result = list_one | compare_lists(list_two) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result|tojson }}
            """,
        ),
        Filter(
            name="json_decode_dict",
            expected={"ret": {"b'a'": "b'b'", "b'c'": "b'd'"}},
            sls="""
            {% set dict_one = {'a': 'b', 'c': 'd'} %}

            {% set result = dict_one | json_decode_dict() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="json_decode_list",
            expected={"ret": ["b'a'", "b'b'", "b'c'", "b'd'"]},
            sls="""
            {% set list_one = ['a', 'b', 'c', 'd'] %}

            {% set result = list_one | json_decode_list() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="json_encode_dict",
            expected={"ret": {"b'a'": "b'b'", "b'c'": "b'd'"}},
            sls="""
            {% set dict_one = {'a': 'b', 'c': 'd'} %}

            {% set result = dict_one | json_encode_dict() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="json_encode_list",
            expected={"ret": ["b'a'", "b'b'", "b'c'", "b'd'"]},
            sls="""
            {% set list_one = ['a', 'b', 'c', 'd'] %}

            {% set result = list_one | json_encode_list() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="exactly_n_true",
            expected={"ret": True},
            sls="""
            {% set list = [True, False, False, True] %}

            {% set result = list | exactly_n_true(2) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="exactly_one_true",
            expected={"ret": True},
            sls="""
            {% set list = [True, False, False, False] %}

            {% set result = list | exactly_one_true() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="is_iter",
            expected={"ret": True},
            sls="""
            {% set list = ['abcd','efgh','ijk','lmno','pqrs'] %}

            {% set result = list | is_iter() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="is_list",
            expected={"ret": True},
            sls="""
            {% set list = ['abcd','efgh','ijk','lmno','pqrs'] %}

            {% set result = list | is_list() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="mysql_to_dict",
            expected={
                "ret": {
                    "show processlist": {
                        "Info": "show processlist",
                        "db": "NULL",
                        "Host": "localhost",
                        "State": "init",
                        "Command": "Query",
                        "User": "root",
                        "Time": 0,
                        "Id": 7,
                    }
                }
            },
            sls="""
            {% set test_mysql_output =  ['+----+------+-----------+------+---------+------+-------+------------------+',
                                         '| Id | User | Host      | db   | Command | Time | State | Info             |',
                                         '+----+------+-----------+------+---------+------+-------+------------------+',
                                         '|  7 | root | localhost | NULL | Query   |    0 | init  | show processlist |',
                                         '+----+------+-----------+------+---------+------+-------+------------------+'] %}

            {% set result = test_mysql_output | mysql_to_dict('Info') %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result|tojson }}
            """,
        ),
        Filter(
            name="sorted_ignorecase",
            expected={"ret": ["Abcd", "efgh", "Ijk", "lmno", "Pqrs"]},
            sls="""
            {% set list = ['lmno','efgh','Ijk','Pqrs','Abcd'] %}

            {% set result = list | sorted_ignorecase() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="substring_in_list",
            expected={"ret": True},
            sls="""
            {% set string = 'lmno' %}
            {% set list = ['abcd','efgh','ijk','lmno','pqrs'] %}

            {% set result = string | substring_in_list(list) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="strftime",
            sls="""
            {% set result = none | strftime('%Y-%m-%d') %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="is_bin_file",
            expected={"ret": True},
            sls=r"""
            {% if grains['os'] == 'Windows' %}
              {% set result = 'c:\Windows\System32\cmd.exe' | is_bin_file() %}
            {% else %}
              {% set result = '/bin/ls' | is_bin_file() %}
            {% endif %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="base64_decode",
            expected={"ret": "Salt Rocks!"},
            sls="""
            {% set result = 'U2FsdCBSb2NrcyE=' | base64_decode() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="base64_encode",
            expected={"ret": "U2FsdCBSb2NrcyE="},
            sls="""
            {% set result = 'Salt Rocks!' | base64_encode() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        EmptyFileFilter(),
        TextFileFilter(),
        ListFilesFilter(),
        FileHashsumFilter(),
        Filter(
            name="hmac",
            expected={"ret": True},
            sls="""
            {% set result = 'Salt Rocks!' | hmac(shared_secret='topsecret', challenge_hmac='nMgLxwHPFyRgGfunkXXAI3Z/ZR4p5lmPTUjk2eGDqks=') %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="md5",
            expected={"ret": "85d6e71db655ee8e42c8b18475f0925f"},
            sls="""
            {% set result = 'Salt Rocks!' | md5() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="random_hash",
            sls="""
            {% set result = 9999999999 | random_hash() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="sha256",
            expected={
                "ret": "cce7fe00fd9cc6122fd3b2ed22feae215bcfe7ac4a7879d336c1993426a763fe"
            },
            sls="""
            {% set result = 'Salt Rocks!' | sha256() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="sha512",
            expected={
                "ret": "44d829491d8caa7039ad08a5b7fa9dd0f930138c614411c5326dd4755fdc9877ec6148219fccbe404139e7bb850e77237429d64f560c204f3697ab489fd8bfa5"
            },
            sls="""
            {% set result = 'Salt Rocks!' | sha512() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="http_query",
            expected={"ret": {}},
            sls="""
            {% set result = 'https://www.google.com' | http_query(test=True) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="avg",
            expected={"ret": 2.5},
            sls="""
            {% set result = [1, 2, 3, 4] | avg() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="difference",
            expected={"ret": [1, 3]},
            sls="""
            {% set result = [1, 2, 3, 4] | difference([2, 4, 6]) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="intersect",
            expected={"ret": [2, 4]},
            sls="""
            {% set result = [1, 2, 3, 4] | intersect([2, 4, 6]) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="max",
            expected={"ret": 4},
            sls="""
            {% set result = [1, 2, 3, 4] | max() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="min",
            expected={"ret": 1},
            sls="""
            {% set result = [1, 2, 3, 4] | min() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="quote",
            expected={"ret": "Salt Rocks!"},
            sls="""
            {% set result = 'Salt Rocks!' | quote() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="regex_escape",
            expected={"ret": r"Salt\ Rocks"},
            sls="""
            {% set result = 'Salt Rocks' | regex_escape() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="regex_match",
            expected={"ret": "('a', 'd')"},
            sls="""
            {% set result = 'abcd' | regex_match('^(.*)BC(.*)$', ignorecase=True) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="regex_replace",
            expected={"ret": "lets__replace__spaces"},
            sls=r"""
            {% set result = 'lets replace spaces' | regex_replace('\s+', '__') %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="regex_search",
            expected={"ret": "('a', 'd')"},
            sls="""
            {% set result = 'abcd' | regex_search('^(.*)BC(.*)$', ignorecase=True) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="sequence",
            expected={"ret": ["Salt Rocks!"]},
            sls="""
            {% set result = 'Salt Rocks!' | sequence() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="skip",
            expected={"ret": None},
            sls="""
            {% set result = 'Salt Rocks!' | skip() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="symmetric_difference",
            expected={"ret": [1, 3, 6]},
            sls="""
            {% set result = [1, 2, 3, 4] | symmetric_difference([2, 4, 6]) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="to_bool",
            expected={"ret": True},
            sls="""
            {% set result = 'yes' | to_bool() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="union",
            expected={"ret": [1, 2, 3, 4, 6]},
            sls="""
            {% set result = [1, 2, 3, 4] | union([2, 4, 6]) %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="unique",
            expected={"ret": ["a", "b", "c"]},
            sls="""
            {% set result = ['a', 'b', 'c', 'a', 'b'] | unique() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="uuid",
            expected={"ret": "799192d9-7f32-5227-a45f-dfeb4a34e06f"},
            sls="""
            {% set result = 'Salt Rocks!' | uuid() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        StartsWithFilter(
            name="gen_mac",
            expected="AC:DE:48:",
            sls="""
            {% set result = 'AC:DE:48' | gen_mac() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        SortedFilter(
            name="ipaddr",
            expected={"ret": ["127.0.0.1", "::1"]},
            sls="""
            {% set result = 'Salt Rocks!' | uuid() %}
            {% set result = ['127.0.0.1', '::1', 'random_junk'] | ipaddr() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="ip_host",
            expected={"ret": "192.168.0.12/24"},
            sls="""
            {% set result = '192.168.0.12/24' | ip_host() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="ipv4",
            expected={"ret": ["127.0.0.1"]},
            sls="""
            {% set result = ['127.0.0.1', '::1'] | ipv4() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="ipv6",
            expected={"ret": ["::1"]},
            sls="""
            {% set result = ['127.0.0.1', '::1'] | ipv6() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="is_ip",
            expected={"ret": True},
            sls="""
            {% set result = '127.0.0.1' | is_ip() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="is_ipv4",
            expected={"ret": True},
            sls="""
            {% set result = '127.0.0.1' | is_ipv4() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="is_ipv6",
            expected={"ret": True},
            sls="""
            {% set result = '::1' | is_ipv6() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="network_hosts",
            expected={"ret": ["192.168.1.1", "192.168.1.2"]},
            sls="""
            {% set result = '192.168.1.0/30' | network_hosts() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="network_size",
            expected={"ret": 16},
            sls="""
            {% set result = '192.168.1.0/28' | network_size() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="path_join",
            expected={"ret": os.path.sep + os.path.join("a", "b", "c", "d")},
            sls="""
            {% set result = '/a/b/c' | path_join('d') %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="which",
            expected={"ret": salt.utils.path.which("which")},
            sls="""
            {% set result = 'which' | which() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="contains_whitespace",
            expected={"ret": True},
            sls="""
            {% set result = 'This string has whitespace' | contains_whitespace() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="is_hex",
            expected={"ret": True},
            sls="""
            {% set result = '0x2a' | is_hex() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="random_str",
            expected=lambda x: len(x["ret"]) == 32,
            sls="""
            {% set result = 32 | random_str() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="to_num",
            expected={"ret": 42},
            sls="""
            {% set result = '42' | to_num() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="check_whitelist_blacklist",
            expected={"ret": True},
            sls="""
            {% set result = 'string' | check_whitelist_blacklist(whitelist='string') %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        SkipOnWindowsFilter(
            name="get_uid",
            expected={"ret": 0},
            sls="""
            {% set result = 'root' | get_uid() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="yaml_dquote",
            expected={"ret": "A double-quoted string in YAML"},
            sls="""
            {% set result = "A double-quoted string in YAML" | yaml_dquote() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="yaml_squote",
            expected={"ret": "A single-quoted string in YAML"},
            sls="""
            {% set result = 'A single-quoted string in YAML' | yaml_squote() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="yaml_encode",
            expected={"ret": "An encoded string in YAML"},
            sls="""
            {% set result = "An encoded string in YAML" | yaml_encode() %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="yaml",
            expected={"ret": {"Question": "Quieres Café?"}},
            sls="""
            {% set result = {"Question": "Quieres Café?"} | yaml %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
        Filter(
            name="json",
            expected={"ret": {"Question": "Quieres Café?"}},
            sls="""
            {% set result = {"Question": "Quieres Café?"} | json %}
            test:
              module.run:
                - name: test.echo
                - text: {{ result }}
            """,
        ),
    ],
    ids=_filter_id,
)
def filter(request):
    return request.param


def test_filter(state, state_tree, filter, grains):
    filter.check_skip(grains)
    with filter(state_tree):
        ret = state.sls("filter")
        log.debug("state.sls returned: %s", ret)
        assert not ret.failed
        for state_result in ret:
            assert state_result.result is True
            filter.assert_result(state_result.changes)

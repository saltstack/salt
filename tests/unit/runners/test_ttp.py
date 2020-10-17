"""
    :codeauthor: Denis Mulyalin <d.mulyalin@gmail.com>
"""
import salt.runners.ttp as ttp_module

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase
from salt.exceptions import CommandExecutionError


class TTPRunnerModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {
            "__salt__": {},
            "__opts__": {"id": "master", "timeout": 100},
        }

        return {ttp_module: module_globals}

    def test_ttp_run_minion_inline_command(self):
        ttp_template = """
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                res = ttp_module.run(
                    "minion_1",
                    "cmd.run",
                    "hostnamectl",
                    template="salt://ttp/test_template_1.txt",
                )
                assert res == [
                    [
                        {
                            "chassis": "vm",
                            "hostname": "localhost.localdomain",
                            "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                            "os": "CentOS Linux 7 (Core)",
                        }
                    ]
                ]

    def test_ttp_run_minion_inline_command_flat_list(self):
        ttp_template = """
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                res = ttp_module.run(
                    "minion_1",
                    "cmd.run",
                    "hostnamectl",
                    template="salt://ttp/test_template_1.txt",
                    ttp_res_kwargs={"structure": "flat_list"},
                )
                assert res == [
                    {
                        "chassis": "vm",
                        "hostname": "localhost.localdomain",
                        "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                        "os": "CentOS Linux 7 (Core)",
                    }
                ]

    def test_ttp_run_fail_template_file_load(self):
        """
        This test returns None for "cp.get_file_str" simulating
        wrong path to or non existing template raising CommandExecutionError
        dues to "template_text" is None
        """
        mock_cp_get_file_str = MagicMock(return_value=None)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            self.assertRaises(
                CommandExecutionError,
                ttp_module.run,
                "minion_1",
                "cmd.run",
                "hostnamectl",
                template="salt://ttp/test_template_1.txt",
            )

    def test_ttp_run_template_fail_to_load(self):
        """
        This test loads badly formatted template, causing
        CommandExecutionError for "parser.add_template(template_text)"
        call
        """
        broken_template = """
<group name="bla">
 Static hostname: {{ hostname }}
<
        """
        mock_cp_get_file_str = MagicMock(return_value=broken_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            self.assertRaises(
                CommandExecutionError,
                ttp_module.run,
                "minion_1",
                "cmd.run",
                "hostnamectl",
                template="salt://ttp/test_template_1.txt",
            )

    def test_ttp_run_fail_to_parse(self):
        """
        This template raises exception within template macro trigerring
        CommandExecutionError for "parser.parse(one=True)" call
        """
        ttp_template = """
<macro>
def raise_error(data):
    raise NameError('HiThere, testing exception')
</macro>

<group macro="raise_error">
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
</group>
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                self.assertRaises(
                    CommandExecutionError,
                    ttp_module.run,
                    "minion_1",
                    "cmd.run",
                    "hostnamectl",
                    template="salt://ttp/test_template_1.txt",
                )

    def test_ttp_run_net_cli_output(self):
        ttp_template = """
<group name="system">
hostname {{ hostname }}
</group>

<vars>sysname="gethostname"</vars>

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
{{ system_name | set("sysname") }}
</group>
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": {
                        "out": {
                            "show run | inc hostname": """
hostname RT-CORE-1 
                            """,
                            "show run | sec interface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                            """,
                        }
                    }
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                res = ttp_module.run(
                    "minion_1",
                    "net.cli",
                    "show run | inc hostname",
                    "show run | sec interface",
                    template="salt://ttp/test_template_1.txt",
                )
                assert res == [
                    [
                        {
                            "interfaces": [
                                {
                                    "description": "core381:Eth1/32",
                                    "interface": "Eth1/1",
                                    "system_name": "minion_1",
                                },
                                {
                                    "description": "chas012-sw1",
                                    "interface": "Eth1/2",
                                    "system_name": "minion_1",
                                },
                            ],
                            "system": {"hostname": "RT-CORE-1"},
                        }
                    ]
                ]

    def test_ttp_run_nr_cli_output(self):
        ttp_template = """
<group name="system">
hostname {{ hostname }}
</group>

<vars>sysname="gethostname"</vars>

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
{{ system_name | set("sysname") }}
</group>
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": {
                        "minion_111": {
                            "show run | inc hostname": """
hostname RT-CORE-1 
                            """,
                            "show run | sec interface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                            """,
                        },
                        "minion_222": {
                            "show run | inc hostname": """
hostname RT-CORE-341
                            """,
                            "show run | sec interface": """
interface Eth1/35
 description core389:Eth1/36
interface Eth1/22
 description chas0121-sw11
                            """,
                        },
                    }
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                res = ttp_module.run(
                    "nornir_minion",
                    "nr.cli",
                    "show run | inc hostname",
                    "show run | sec interface",
                    template="salt://ttp/test_template_1.txt",
                )
                assert res == [
                    [
                        {
                            "interfaces": [
                                {
                                    "description": "core381:Eth1/32",
                                    "interface": "Eth1/1",
                                    "system_name": "minion_111",
                                },
                                {
                                    "description": "chas012-sw1",
                                    "interface": "Eth1/2",
                                    "system_name": "minion_111",
                                },
                            ],
                            "system": {"hostname": "RT-CORE-1"},
                        },
                        {
                            "interfaces": [
                                {
                                    "description": "core389:Eth1/36",
                                    "interface": "Eth1/35",
                                    "system_name": "minion_222",
                                },
                                {
                                    "description": "chas0121-sw11",
                                    "interface": "Eth1/22",
                                    "system_name": "minion_222",
                                },
                            ],
                            "system": {"hostname": "RT-CORE-341"},
                        },
                    ]
                ]

    def test_ttp_run_mine_get_napalm_proxy_net_cli(self):
        """
        To test that TTP can parse mine.get output for net.cli
        function
        """
        ttp_template = """
<group name="system">
hostname {{ hostname }}
</group>

<vars>sysname="gethostname"</vars>

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
{{ system_name | set("sysname") }}
</group>
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": {
                        "minion_1": {
                            "out": {
                                "show run | inc hostname": """
hostname RT-CORE-1 
                                """,
                                "show run | sec interface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                                """,
                            }
                        }
                    }
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock_cmd_iter(*args, **kwargs):
                    return data_to_parse

                def mock_cmd(*args, **kwargs):
                    return {"minion_1": {"proxy": {"proxytype": "napalm"}}}

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock_cmd_iter
                MockClient.cmd = mock_cmd

                # Simulate TTP run command
                res = ttp_module.run(
                    "minion_1",
                    "mine.get",
                    "minion_1",
                    "net.cli",
                    template="salt://ttp/test_template_1.txt",
                )
                assert res == [
                    [
                        {
                            "interfaces": [
                                {
                                    "description": "core381:Eth1/32",
                                    "interface": "Eth1/1",
                                    "system_name": "minion_1",
                                },
                                {
                                    "description": "chas012-sw1",
                                    "interface": "Eth1/2",
                                    "system_name": "minion_1",
                                },
                            ],
                            "system": {"hostname": "RT-CORE-1"},
                        }
                    ]
                ]

    def test_ttp_run_mine_get_nornir_proxy_nr_cli(self):
        ttp_template = """
<group name="system">
hostname {{ hostname }}
</group>

<vars>sysname="gethostname"</vars>

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
{{ system_name | set("sysname") }}
</group>
        """
        data_to_parse = [
            {
                "nornir_minion": {
                    "ret": {
                        "nornir_minion": {
                            "minion_111": {
                                "show run | inc hostname": """
hostname RT-CORE-1 
                            """,
                                "show run | sec interface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                            """,
                            },
                            "minion_222": {
                                "show run | inc hostname": """
hostname RT-CORE-341
                            """,
                                "show run | sec interface": """
interface Eth1/35
 description core389:Eth1/36
interface Eth1/22
 description chas0121-sw11
                            """,
                            },
                        }
                    }
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock_cmd_iter(*args, **kwargs):
                    return data_to_parse

                def mock_cmd(*args, **kwargs):
                    return {"nornir_minion": {"proxy": {"proxytype": "nornir"}}}

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock_cmd_iter
                MockClient.cmd = mock_cmd

                # Simulate TTP run command
                res = ttp_module.run(
                    "nornir_minion",
                    "mine.get",
                    "nornir_minion",
                    template="salt://ttp/test_template_1.txt",
                )
                assert res == [
                    [
                        {
                            "interfaces": [
                                {
                                    "description": "core381:Eth1/32",
                                    "interface": "Eth1/1",
                                    "system_name": "minion_111",
                                },
                                {
                                    "description": "chas012-sw1",
                                    "interface": "Eth1/2",
                                    "system_name": "minion_111",
                                },
                            ],
                            "system": {"hostname": "RT-CORE-1"},
                        },
                        {
                            "interfaces": [
                                {
                                    "description": "core389:Eth1/36",
                                    "interface": "Eth1/35",
                                    "system_name": "minion_222",
                                },
                                {
                                    "description": "chas0121-sw11",
                                    "interface": "Eth1/22",
                                    "system_name": "minion_222",
                                },
                            ],
                            "system": {"hostname": "RT-CORE-341"},
                        },
                    ]
                ]

    def test_ttp_run_elc_ttp_custom_returner(self):
        ttp_template = """
<group>
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
</group>

<output>
returner = "elasticsearch"
index = "intf_counters_test"
</output>
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {
                "salt.cmd": mock_cp_get_file_str,
                "elasticsearch.document_create": MagicMock(return_value=True),
            },
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                res = ttp_module.run(
                    "minion_1",
                    "cmd.run",
                    "hostnamectl",
                    template="salt://ttp/test_template_1.txt",
                )
                assert res == [
                    [
                        [
                            {
                                "chassis": "vm",
                                "hostname": "localhost.localdomain",
                                "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                                "os": "CentOS Linux 7 (Core)",
                            }
                        ]
                    ]
                ]

    def test_ttp_run_custom_vars_injection_in_ttp_vars(self):
        ttp_template = """
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
{{ custom_var1 | set("var1") }}
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                res = ttp_module.run(
                    "minion_1",
                    "cmd.run",
                    "hostnamectl",
                    template="salt://ttp/test_template_1.txt",
                    vars={"var1": "val1"},
                )
                assert res == [
                    [
                        {
                            "chassis": "vm",
                            "hostname": "localhost.localdomain",
                            "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                            "os": "CentOS Linux 7 (Core)",
                            "custom_var1": "val1",
                        }
                    ]
                ]

    def test_ttp_run_minion_template_with_inputs(self):
        ttp_template = """
<input name="sys_host">
tgt = "minion_1"
fun = "cmd.run"
arg = ['hostnamectl']
kwarg = {}
tgt_type = "glob"
</input>
    
<group name="system" input="sys_host">
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
</group>
        """
        data_to_parse = [
            {
                "minion_1": {
                    "ret": """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
                }
            }
        ]
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        with patch.dict(
            ttp_module.__salt__,
            {"salt.cmd": mock_cp_get_file_str},
        ):
            with patch.object(ttp_module, "client", MagicMock()) as MockClient:

                def mock(*args, **kwargs):
                    return data_to_parse

                # ttp getting results by calling:
                # inline_cmd_results = client.cmd_iter(*args, **kwargs)
                # below we creating dummy "cmd_iter" method for MockClient
                MockClient.cmd_iter = mock

                # Simulate TTP run command
                res = ttp_module.run("salt://ttp/test_template_1.txt")

                assert res == [
                    [
                        {
                            "system": {
                                "chassis": "vm",
                                "hostname": "localhost.localdomain",
                                "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                                "os": "CentOS Linux 7 (Core)",
                            }
                        }
                    ]
                ]

"""
    :codeauthor: Denis Mulyalin <d.mulyalin@gmail.com>
"""
import salt.modules.ttp as ttp_module

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase
from salt.exceptions import CommandExecutionError


class TTPModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {"__salt__": {}, "__opts__": {"id": "test_minion_id"}}

        return {ttp_module: module_globals}

    def test_ttp_run_minion_inline_command(self):
        ttp_template = """
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
        """
        data_to_parse = """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"cmd.run": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            res = ttp_module.run(
                "cmd.run", "hostnamectl", template="salt://ttp/test_template_1.txt"
            )
            assert res == [
                [
                    {
                        "os": "CentOS Linux 7 (Core)",
                        "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                        "chassis": "vm",
                        "hostname": "localhost.localdomain",
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
        data_to_parse = """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"cmd.run": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            res = ttp_module.run(
                "cmd.run",
                "hostnamectl",
                template="salt://ttp/test_template_1.txt",
                ttp_res_kwargs={"structure": "flat_list"},
            )
            assert res == [
                {
                    "os": "CentOS Linux 7 (Core)",
                    "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                    "chassis": "vm",
                    "hostname": "localhost.localdomain",
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
            {"cp.get_file_str": mock_cp_get_file_str},
        ):
            self.assertRaises(
                CommandExecutionError,
                ttp_module.run,
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
            {"cp.get_file_str": mock_cp_get_file_str},
        ):
            self.assertRaises(
                CommandExecutionError,
                ttp_module.run,
                "cmd.run",
                "hostnamectl",
                template="salt://ttp/test_template.txt",
            )

    def test_ttp_run_fail_to_parse(self):
        """
        This template raises exception withoint template macro trigerring
        causing CommandExecutionError fpr "parser.parse(one=True)" call
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
        data_to_parse = """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"cmd.run": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            self.assertRaises(
                CommandExecutionError,
                ttp_module.run,
                "cmd.run",
                "hostnamectl",
                template="salt://ttp/test_template.txt",
            )

    def test_ttp_run_template_with_imputs(self):
        ttp_template = """
<input>
fun = "cmd.run"
arg = ['hostnamectl']
kwarg = {}
</input>

<group name="system">
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
</group>
        """
        data_to_parse = """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"cmd.run": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            res = ttp_module.run(template="salt://ttp/test_template_1.txt")
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

    def test_ttp_run_net_cli_output(self):
        ttp_template = """
<group name="system">
hostname {{ hostname }}
</group>

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
</group>
        """
        data_to_parse = {
            "out": {
                "show run | inc hostname": """
hostname RT-CORE-1 
                """,
                "show run | sec interrface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                """,
            }
        }
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"net.cli": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            res = ttp_module.run(
                "net.cli",
                "show run | inc hostname",
                "show run | sec interrface",
                template="salt://ttp/test_template_1.txt",
            )
            assert res == [
                [
                    {
                        "interfaces": [
                            {"description": "core381:Eth1/32", "interface": "Eth1/1"},
                            {"description": "chas012-sw1", "interface": "Eth1/2"},
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

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
</group>
        """
        data_to_parse = {
            "RT-CORE-1": {
                "show run | inc hostname": """
hostname RT-CORE-1 
                """,
                "show run | sec interrface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                """,
            },
            "RT-CORE-2": {
                "show run | inc hostname": """
hostname RT-CORE-2
                """,
                "show run | sec interrface": """
interface Eth1/11
 description core382:Eth1/34
interface Eth1/22
 description chas011-sw2
                """,
            },
        }
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"nr.cli": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            res = ttp_module.run(
                "nr.cli",
                "show run | inc hostname",
                "show run | sec interrface",
                template="salt://ttp/test_template_1.txt",
            )
            assert res == [
                [
                    {
                        "interfaces": [
                            {"description": "core381:Eth1/32", "interface": "Eth1/1"},
                            {"description": "chas012-sw1", "interface": "Eth1/2"},
                        ],
                        "system": {"hostname": "RT-CORE-1"},
                    },
                    {
                        "interfaces": [
                            {"description": "core382:Eth1/34", "interface": "Eth1/11"},
                            {"description": "chas011-sw2", "interface": "Eth1/22"},
                        ],
                        "system": {"hostname": "RT-CORE-2"},
                    },
                ]
            ]

    def test_ttp_run_mine_get_napalm_proxy_net_cli(self):
        ttp_template = """
<group name="system">
hostname {{ hostname }}
</group>

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
</group>
        """
        data_to_parse = {
            "proxy_minion_1": {
                "out": {
                    "show run | inc hostname": """
hostname RT-CORE-1 
                """,
                    "show run | sec interrface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                """,
                }
            }
        }
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"mine.get": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            with patch.dict(
                ttp_module.__pillar__,
                {"proxy": {"proxytype": "napalm"}},
            ):
                # Simulate TTP run command
                res = ttp_module.run(
                    "mine.get",
                    "proxy_minion_1",
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
                                },
                                {"description": "chas012-sw1", "interface": "Eth1/2"},
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

<group name="interfaces">
interface {{ interface }}
 description {{ description }}
</group>
        """
        data_to_parse = {
            "proxy_minion_1": {
                "RT-CORE-1": {
                    "show run | inc hostname": """
hostname RT-CORE-1 
                """,
                    "show run | sec interrface": """
interface Eth1/1
 description core381:Eth1/32
interface Eth1/2
 description chas012-sw1
                """,
                },
                "RT-CORE-2": {
                    "show run | inc hostname": """
hostname RT-CORE-2
                """,
                    "show run | sec interrface": """
interface Eth1/11
 description core382:Eth1/34
interface Eth1/22
 description chas011-sw2
                """,
                },
            }
        }
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"mine.get": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            with patch.dict(
                ttp_module.__pillar__,
                {"proxy": {"proxytype": "nornir"}},
            ):
                # Simulate TTP run command
                res = ttp_module.run(
                    "mine.get",
                    "proxy_minion_1",
                    "nr.cli",
                    template="salt://ttp/test_template_1.txt",
                )
                assert res == [
                    [
                        {
                            "interfaces": [
                                {
                                    "description": "core381:Eth1/32",
                                    "interface": "Eth1/1",
                                },
                                {"description": "chas012-sw1", "interface": "Eth1/2"},
                            ],
                            "system": {"hostname": "RT-CORE-1"},
                        },
                        {
                            "interfaces": [
                                {
                                    "description": "core382:Eth1/34",
                                    "interface": "Eth1/11",
                                },
                                {"description": "chas011-sw2", "interface": "Eth1/22"},
                            ],
                            "system": {"hostname": "RT-CORE-2"},
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
        data_to_parse = """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {
                "cmd.run": mock_cmd_run,
                "cp.get_file_str": mock_cp_get_file_str,
                "elasticsearch.document_create": MagicMock(return_value=True),
            },
        ):
            # Simulate TTP run command
            res = ttp_module.run(
                "cmd.run", "hostnamectl", template="salt://ttp/test_template_1.txt"
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

    def test_ttp_run_minion_id_injection_in_ttp_vars(self):
        ttp_template = """
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
{{ minon_id | set("_minion_id_") }}
        """
        data_to_parse = """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"cmd.run": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            res = ttp_module.run(
                "cmd.run", "hostnamectl", template="salt://ttp/test_template_1.txt"
            )
            assert res == [
                [
                    {
                        "chassis": "vm",
                        "hostname": "localhost.localdomain",
                        "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                        "minon_id": "test_minion_id",
                        "os": "CentOS Linux 7 (Core)",
                    }
                ]
            ]

    def test_ttp_run_custom_vars_injection_in_ttp_vars(self):
        ttp_template = """
 Static hostname: {{ hostname }}
         Chassis: {{ chassis }}
      Machine ID: {{ machine_id }}
Operating System: {{ os | ORPHRASE }}
{{ cust_var_1 | set("var1") }}
        """
        data_to_parse = """
 Static hostname: localhost.localdomain
         Chassis: vm
      Machine ID: 2a26648f68764152a772fc20c9a3ddb3
Operating System: CentOS Linux 7 (Core)
        """
        mock_cp_get_file_str = MagicMock(return_value=ttp_template)
        mock_cmd_run = MagicMock(return_value=data_to_parse)
        with patch.dict(
            ttp_module.__salt__,
            {"cmd.run": mock_cmd_run, "cp.get_file_str": mock_cp_get_file_str},
        ):
            # Simulate TTP run command
            res = ttp_module.run(
                "cmd.run",
                "hostnamectl",
                template="salt://ttp/test_template_1.txt",
                vars={"var1": "val1", "a": "b"},
            )
            assert res == [
                [
                    {
                        "chassis": "vm",
                        "cust_var_1": "val1",
                        "hostname": "localhost.localdomain",
                        "machine_id": "2a26648f68764152a772fc20c9a3ddb3",
                        "os": "CentOS Linux 7 (Core)",
                    }
                ]
            ]

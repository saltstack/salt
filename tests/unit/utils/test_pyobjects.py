# -*- coding: utf-8 -*-

# Import Pytohn libs
from __future__ import absolute_import

import logging
import os
import shutil
import tempfile
import textwrap
import uuid

import jinja2

# Import Salt libs
import salt.config
import salt.state
import salt.utils.files
from salt.template import compile_template
from salt.utils.odict import OrderedDict
from salt.utils.pyobjects import (
    DuplicateState,
    InvalidFunction,
    Registry,
    SaltObject,
    State,
    StateFactory,
)
from tests.support.runtests import RUNTIME_VARS

# Import Salt Testing libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)

File = StateFactory("file")
Service = StateFactory("service")

pydmesg_expected = {
    "file.managed": [
        {"group": "root"},
        {"mode": "0755"},
        {"require": [{"file": "/usr/local/bin"}]},
        {"source": "salt://debian/files/pydmesg.py"},
        {"user": "root"},
    ]
}
pydmesg_salt_expected = OrderedDict([("/usr/local/bin/pydmesg", pydmesg_expected)])
pydmesg_kwargs = dict(
    user="root", group="root", mode="0755", source="salt://debian/files/pydmesg.py"
)

basic_template = """#!pyobjects
File.directory('/tmp', mode='1777', owner='root', group='root')
"""

invalid_template = """#!pyobjects
File.fail('/tmp')
"""

include_template = """#!pyobjects
include('http')
"""

extend_template = """#!pyobjects
include('http')

from salt.utils.pyobjects import StateFactory
Service = StateFactory('service')

Service.running(extend('apache'), watch=[{'file': '/etc/file'}])
"""

map_prefix = """\
#!pyobjects
from salt.utils.pyobjects import StateFactory
Service = StateFactory('service')

{% macro priority(value) %}
    priority = {{ value }}
{% endmacro %}
class Samba(Map):
"""

map_suffix = """
with Pkg.installed("samba", names=[Samba.server, Samba.client]):
    Service.running("samba", name=Samba.service)
"""

map_data = {
    "debian": "    class Debian:\n"
    "        server = 'samba'\n"
    "        client = 'samba-client'\n"
    "        service = 'samba'\n",
    "centos": "    class RougeChapeau:\n"
    "        __match__ = 'RedHat'\n"
    "        server = 'samba'\n"
    "        client = 'samba'\n"
    "        service = 'smb'\n",
    "ubuntu": "    class Ubuntu:\n"
    "        __grain__ = 'os'\n"
    "        service = 'smbd'\n",
}

import_template = """#!pyobjects
import salt://map.sls

Pkg.removed("samba-imported", names=[map.Samba.server, map.Samba.client])
"""

recursive_map_template = """#!pyobjects
from salt://map.sls import Samba

class CustomSamba(Samba):
    pass
"""

recursive_import_template = """#!pyobjects
from salt://recursive_map.sls import CustomSamba

Pkg.removed("samba-imported", names=[CustomSamba.server, CustomSamba.client])"""

scope_test_import_template = """#!pyobjects
from salt://recursive_map.sls import CustomSamba

# since we import CustomSamba we should shouldn't be able to see Samba
Pkg.removed("samba-imported", names=[Samba.server, Samba.client])"""

from_import_template = """#!pyobjects
# this spacing is like this on purpose to ensure it's stripped properly
from   salt://map.sls  import     Samba

Pkg.removed("samba-imported", names=[Samba.server, Samba.client])
"""

import_as_template = """#!pyobjects
from salt://map.sls import Samba as Other
Pkg.removed("samba-imported", names=[Other.server, Other.client])
"""

random_password_template = """#!pyobjects
import random, string
password = ''.join([random.SystemRandom().choice(
        string.ascii_letters + string.digits) for _ in range(20)])
"""

random_password_import_template = """#!pyobjects
from salt://password.sls import password
"""

requisite_implicit_list_template = """#!pyobjects
from salt.utils.pyobjects import StateFactory
Service = StateFactory('service')

with Pkg.installed("pkg"):
    Service.running("service", watch=File("file"), require=Cmd("cmd"))
"""


class MapBuilder(object):
    def build_map(self, template=None):
        """
        Build from a specific template or just use a default if no template
        is passed to this function.
        """
        if template is None:
            template = textwrap.dedent(
                """\
                {{ ubuntu }}
                {{ centos }}
                {{ debian }}
                """
            )
        full_template = map_prefix + template + map_suffix
        ret = jinja2.Template(full_template).render(**map_data)
        log.debug("built map: \n%s", ret)
        return ret


class StateTests(TestCase):
    def setUp(self):
        Registry.empty()

    def test_serialization(self):
        f = State(
            "/usr/local/bin/pydmesg",
            "file",
            "managed",
            require=File("/usr/local/bin"),
            **pydmesg_kwargs
        )

        self.assertEqual(f(), pydmesg_expected)

    def test_factory_serialization(self):
        File.managed(
            "/usr/local/bin/pydmesg", require=File("/usr/local/bin"), **pydmesg_kwargs
        )

        self.assertEqual(Registry.states["/usr/local/bin/pydmesg"], pydmesg_expected)

    def test_context_manager(self):
        with File("/usr/local/bin"):
            pydmesg = File.managed("/usr/local/bin/pydmesg", **pydmesg_kwargs)

            self.assertEqual(
                Registry.states["/usr/local/bin/pydmesg"], pydmesg_expected
            )

            with pydmesg:
                File.managed("/tmp/something", owner="root")

                self.assertEqual(
                    Registry.states["/tmp/something"],
                    {
                        "file.managed": [
                            {"owner": "root"},
                            {
                                "require": [
                                    {"file": "/usr/local/bin"},
                                    {"file": "/usr/local/bin/pydmesg"},
                                ]
                            },
                        ]
                    },
                )

    def test_salt_data(self):
        File.managed(
            "/usr/local/bin/pydmesg", require=File("/usr/local/bin"), **pydmesg_kwargs
        )

        self.assertEqual(Registry.states["/usr/local/bin/pydmesg"], pydmesg_expected)

        self.assertEqual(Registry.salt_data(), pydmesg_salt_expected)

        self.assertEqual(Registry.states, OrderedDict())

    def test_duplicates(self):
        def add_dup():
            File.managed("dup", name="/dup")

        add_dup()
        self.assertRaises(DuplicateState, add_dup)

        Service.running("dup", name="dup-service")

        self.assertEqual(
            Registry.states,
            OrderedDict(
                [
                    (
                        "dup",
                        OrderedDict(
                            [
                                ("file.managed", [{"name": "/dup"}]),
                                ("service.running", [{"name": "dup-service"}]),
                            ]
                        ),
                    )
                ]
            ),
        )


class RendererMixin(object):
    """
    This is a mixin that adds a ``.render()`` method to render a template

    It must come BEFORE ``TestCase`` in the declaration of your test case
    class so that our setUp & tearDown get invoked first, and super can
    trigger the methods in the ``TestCase`` class.
    """

    def setUp(self, *args, **kwargs):
        super(RendererMixin, self).setUp(*args, **kwargs)

        self.root_dir = tempfile.mkdtemp("pyobjects_test_root", dir=RUNTIME_VARS.TMP)
        self.state_tree_dir = os.path.join(self.root_dir, "state_tree")
        self.cache_dir = os.path.join(self.root_dir, "cachedir")
        if not os.path.isdir(self.root_dir):
            os.makedirs(self.root_dir)

        if not os.path.isdir(self.state_tree_dir):
            os.makedirs(self.state_tree_dir)

        if not os.path.isdir(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.config = salt.config.minion_config(None)
        self.config["root_dir"] = self.root_dir
        self.config["state_events"] = False
        self.config["id"] = "match"
        self.config["file_client"] = "local"
        self.config["file_roots"] = dict(base=[self.state_tree_dir])
        self.config["cachedir"] = self.cache_dir
        self.config["test"] = False

    def tearDown(self, *args, **kwargs):
        shutil.rmtree(self.root_dir)
        del self.config
        super(RendererMixin, self).tearDown(*args, **kwargs)

    def write_template_file(self, filename, content):
        full_path = os.path.join(self.state_tree_dir, filename)
        with salt.utils.files.fopen(full_path, "w") as f:
            f.write(content)
        return full_path

    def render(self, template, opts=None, filename=None):
        if opts:
            self.config.update(opts)

        if not filename:
            filename = ".".join([str(uuid.uuid4()), "sls"])
        full_path = self.write_template_file(filename, template)

        state = salt.state.State(self.config)
        return compile_template(
            full_path,
            state.rend,
            state.opts["renderer"],
            state.opts["renderer_blacklist"],
            state.opts["renderer_whitelist"],
        )


class RendererTests(RendererMixin, StateTests, MapBuilder):
    def test_basic(self):
        ret = self.render(basic_template)
        self.assertEqual(
            ret,
            OrderedDict(
                [
                    (
                        "/tmp",
                        {
                            "file.directory": [
                                {"group": "root"},
                                {"mode": "1777"},
                                {"owner": "root"},
                            ]
                        },
                    ),
                ]
            ),
        )
        self.assertEqual(Registry.states, OrderedDict())

    def test_invalid_function(self):
        def _test():
            self.render(invalid_template)

        self.assertRaises(InvalidFunction, _test)

    def test_include(self):
        ret = self.render(include_template)
        self.assertEqual(ret, OrderedDict([("include", ["http"])]))

    def test_extend(self):
        ret = self.render(
            extend_template, {"grains": {"os_family": "Debian", "os": "Debian"}}
        )
        self.assertEqual(
            ret,
            OrderedDict(
                [
                    ("include", ["http"]),
                    (
                        "extend",
                        OrderedDict(
                            [
                                (
                                    "apache",
                                    {
                                        "service.running": [
                                            {"watch": [{"file": "/etc/file"}]}
                                        ]
                                    },
                                ),
                            ]
                        ),
                    ),
                ]
            ),
        )

    def test_sls_imports(self):
        def render_and_assert(template):
            ret = self.render(
                template, {"grains": {"os_family": "Debian", "os": "Debian"}}
            )

            self.assertEqual(
                ret,
                OrderedDict(
                    [
                        (
                            "samba-imported",
                            {"pkg.removed": [{"names": ["samba", "samba-client"]}]},
                        )
                    ]
                ),
            )

        self.write_template_file("map.sls", self.build_map())
        render_and_assert(import_template)
        render_and_assert(from_import_template)
        render_and_assert(import_as_template)

        self.write_template_file("recursive_map.sls", recursive_map_template)
        render_and_assert(recursive_import_template)

    def test_import_scope(self):
        self.write_template_file("map.sls", self.build_map())
        self.write_template_file("recursive_map.sls", recursive_map_template)

        def do_render():
            ret = self.render(
                scope_test_import_template,
                {"grains": {"os_family": "Debian", "os": "Debian"}},
            )

        self.assertRaises(NameError, do_render)

    def test_random_password(self):
        """Test for https://github.com/saltstack/salt/issues/21796"""
        ret = self.render(random_password_template)

    def test_import_random_password(self):
        """Import test for https://github.com/saltstack/salt/issues/21796"""
        self.write_template_file("password.sls", random_password_template)
        ret = self.render(random_password_import_template)

    def test_requisite_implicit_list(self):
        """Ensure that the implicit list characteristic works as expected"""
        ret = self.render(
            requisite_implicit_list_template,
            {"grains": {"os_family": "Debian", "os": "Debian"}},
        )

        self.assertEqual(
            ret,
            OrderedDict(
                [
                    ("pkg", OrderedDict([("pkg.installed", [])])),
                    (
                        "service",
                        OrderedDict(
                            [
                                (
                                    "service.running",
                                    [
                                        {"require": [{"cmd": "cmd"}, {"pkg": "pkg"}]},
                                        {"watch": [{"file": "file"}]},
                                    ],
                                )
                            ]
                        ),
                    ),
                ]
            ),
        )


class MapTests(RendererMixin, TestCase, MapBuilder):
    maxDiff = None

    debian_grains = {"os_family": "Debian", "os": "Debian"}
    ubuntu_grains = {"os_family": "Debian", "os": "Ubuntu"}
    centos_grains = {"os_family": "RedHat", "os": "CentOS"}

    debian_attrs = ("samba", "samba-client", "samba")
    ubuntu_attrs = ("samba", "samba-client", "smbd")
    centos_attrs = ("samba", "samba", "smb")

    def samba_with_grains(self, template, grains):
        return self.render(template, {"grains": grains})

    def assert_equal(self, ret, server, client, service):
        self.assertDictEqual(
            ret,
            OrderedDict(
                [
                    (
                        "samba",
                        OrderedDict(
                            [
                                ("pkg.installed", [{"names": [server, client]}]),
                                (
                                    "service.running",
                                    [
                                        {"name": service},
                                        {"require": [{"pkg": "samba"}]},
                                    ],
                                ),
                            ]
                        ),
                    )
                ]
            ),
        )

    def assert_not_equal(self, ret, server, client, service):
        try:
            self.assert_equal(ret, server, client, service)
        except AssertionError:
            pass
        else:
            raise AssertionError("both dicts are equal")

    def test_map(self):
        """
        Test declarative ordering
        """
        # With declarative ordering, the ubuntu-specfic service name should
        # override the one inherited from debian.
        template = self.build_map(
            textwrap.dedent(
                """\
            {{ debian }}
            {{ centos }}
            {{ ubuntu }}
            """
            )
        )

        ret = self.samba_with_grains(template, self.debian_grains)
        self.assert_equal(ret, *self.debian_attrs)

        ret = self.samba_with_grains(template, self.ubuntu_grains)
        self.assert_equal(ret, *self.ubuntu_attrs)

        ret = self.samba_with_grains(template, self.centos_grains)
        self.assert_equal(ret, *self.centos_attrs)

        # Switching the order, debian should still work fine but ubuntu should
        # no longer match, since the debian service name should override the
        # ubuntu one.
        template = self.build_map(
            textwrap.dedent(
                """\
            {{ ubuntu }}
            {{ debian }}
            """
            )
        )

        ret = self.samba_with_grains(template, self.debian_grains)
        self.assert_equal(ret, *self.debian_attrs)

        ret = self.samba_with_grains(template, self.ubuntu_grains)
        self.assert_not_equal(ret, *self.ubuntu_attrs)

    def test_map_with_priority(self):
        """
        With declarative ordering, the debian service name would override the
        ubuntu one since debian comes second. This will test overriding this
        behavior using the priority attribute.
        """
        template = self.build_map(
            textwrap.dedent(
                """\
            {{ priority(('os_family', 'os')) }}
            {{ ubuntu }}
            {{ centos }}
            {{ debian }}
            """
            )
        )

        ret = self.samba_with_grains(template, self.debian_grains)
        self.assert_equal(ret, *self.debian_attrs)

        ret = self.samba_with_grains(template, self.ubuntu_grains)
        self.assert_equal(ret, *self.ubuntu_attrs)

        ret = self.samba_with_grains(template, self.centos_grains)
        self.assert_equal(ret, *self.centos_attrs)


class SaltObjectTests(TestCase):
    def test_salt_object(self):
        def attr_fail():
            Salt.fail.blah()

        def times2(x):
            return x * 2

        __salt__ = {"math.times2": times2}

        Salt = SaltObject(__salt__)

        self.assertRaises(AttributeError, attr_fail)
        self.assertEqual(Salt.math.times2, times2)
        self.assertEqual(Salt.math.times2(2), 4)

# -*- coding: utf-8 -*-
# pylint: disable=unused-argument

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.states.jboss7 as jboss7
from salt.exceptions import CommandExecutionError
from salt.ext import six

# Import Salt testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class JBoss7StateTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            jboss7: {
                "__salt__": {
                    "jboss7.read_datasource": MagicMock(),
                    "jboss7.create_datasource": MagicMock(),
                    "jboss7.update_datasource": MagicMock(),
                    "jboss7.remove_datasource": MagicMock(),
                    "jboss7.read_simple_binding": MagicMock(),
                    "jboss7.create_simple_binding": MagicMock(),
                    "jboss7.update_simple_binding": MagicMock(),
                    "jboss7.undeploy": MagicMock(),
                    "jboss7.deploy": MagicMock,
                    "file.get_managed": MagicMock,
                    "file.manage_file": MagicMock,
                    "jboss7.list_deployments": MagicMock,
                },
                "__env__": "base",
            }
        }

    def test_should_not_redeploy_unchanged(self):
        # given
        parameters = {
            "target_file": "some_artifact",
            "undeploy_force": False,
            "undeploy": "some_artifact",
            "source": "some_artifact_on_master",
        }
        jboss_conf = {"cli_path": "somewhere", "controller": "some_controller"}

        def list_deployments(jboss_config):
            return ["some_artifact"]

        def file_get_managed(
            name,
            template,
            source,
            source_hash,
            source_hash_name,
            user,
            group,
            mode,
            attrs,
            saltenv,
            context,
            defaults,
            skip_verify,
            kwargs,
        ):
            return "sfn", "hash", ""

        def file_manage_file(
            name,
            sfn,
            ret,
            source,
            source_sum,
            user,
            group,
            mode,
            attrs,
            saltenv,
            backup,
            makedirs,
            template,
            show_diff,
            contents,
            dir_mode,
        ):
            return {"result": True, "changes": False}

        jboss7_undeploy_mock = MagicMock()
        jboss7_deploy_mock = MagicMock()
        file_get_managed = MagicMock(side_effect=file_get_managed)
        file_manage_file = MagicMock(side_effect=file_manage_file)
        list_deployments_mock = MagicMock(side_effect=list_deployments)
        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.undeploy": jboss7_undeploy_mock,
                "jboss7.deploy": jboss7_deploy_mock,
                "file.get_managed": file_get_managed,
                "file.manage_file": file_manage_file,
                "jboss7.list_deployments": list_deployments_mock,
            },
        ):
            # when
            result = jboss7.deployed(
                name="unchanged", jboss_config=jboss_conf, salt_source=parameters
            )

            # then
            self.assertFalse(jboss7_undeploy_mock.called)
            self.assertFalse(jboss7_deploy_mock.called)

    def test_should_redeploy_changed(self):
        # given
        parameters = {
            "target_file": "some_artifact",
            "undeploy_force": False,
            "undeploy": "some_artifact",
            "source": "some_artifact_on_master",
        }
        jboss_conf = {"cli_path": "somewhere", "controller": "some_controller"}

        def list_deployments(jboss_config):
            return ["some_artifact"]

        def file_get_managed(
            name,
            template,
            source,
            source_hash,
            source_hash_name,
            user,
            group,
            mode,
            attrs,
            saltenv,
            context,
            defaults,
            skip_verify,
            kwargs,
        ):
            return "sfn", "hash", ""

        def file_manage_file(
            name,
            sfn,
            ret,
            source,
            source_sum,
            user,
            group,
            mode,
            attrs,
            saltenv,
            backup,
            makedirs,
            template,
            show_diff,
            contents,
            dir_mode,
        ):
            return {"result": True, "changes": True}

        jboss7_undeploy_mock = MagicMock()
        jboss7_deploy_mock = MagicMock()
        file_get_managed = MagicMock(side_effect=file_get_managed)
        file_manage_file = MagicMock(side_effect=file_manage_file)
        list_deployments_mock = MagicMock(side_effect=list_deployments)
        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.undeploy": jboss7_undeploy_mock,
                "jboss7.deploy": jboss7_deploy_mock,
                "file.get_managed": file_get_managed,
                "file.manage_file": file_manage_file,
                "jboss7.list_deployments": list_deployments_mock,
            },
        ):
            # when
            result = jboss7.deployed(
                name="unchanged", jboss_config=jboss_conf, salt_source=parameters
            )

            # then
            self.assertTrue(jboss7_undeploy_mock.called)
            self.assertTrue(jboss7_deploy_mock.called)

    def test_should_deploy_different_artifact(self):
        # given
        parameters = {
            "target_file": "some_artifact",
            "undeploy_force": False,
            "undeploy": "some_artifact",
            "source": "some_artifact_on_master",
        }
        jboss_conf = {"cli_path": "somewhere", "controller": "some_controller"}

        def list_deployments(jboss_config):
            return ["some_other_artifact"]

        def file_get_managed(
            name,
            template,
            source,
            source_hash,
            source_hash_name,
            user,
            group,
            mode,
            attrs,
            saltenv,
            context,
            defaults,
            skip_verify,
            kwargs,
        ):
            return "sfn", "hash", ""

        def file_manage_file(
            name,
            sfn,
            ret,
            source,
            source_sum,
            user,
            group,
            mode,
            attrs,
            saltenv,
            backup,
            makedirs,
            template,
            show_diff,
            contents,
            dir_mode,
        ):
            return {"result": True, "changes": False}

        jboss7_undeploy_mock = MagicMock()
        jboss7_deploy_mock = MagicMock()
        file_get_managed = MagicMock(side_effect=file_get_managed)
        file_manage_file = MagicMock(side_effect=file_manage_file)
        list_deployments_mock = MagicMock(side_effect=list_deployments)
        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.undeploy": jboss7_undeploy_mock,
                "jboss7.deploy": jboss7_deploy_mock,
                "file.get_managed": file_get_managed,
                "file.manage_file": file_manage_file,
                "jboss7.list_deployments": list_deployments_mock,
            },
        ):
            # when
            result = jboss7.deployed(
                name="unchanged", jboss_config=jboss_conf, salt_source=parameters
            )

            # then
            self.assertFalse(jboss7_undeploy_mock.called)
            self.assertTrue(jboss7_deploy_mock.called)

    def test_should_redploy_undeploy_force(self):
        # given
        parameters = {
            "target_file": "some_artifact",
            "undeploy_force": True,
            "undeploy": "some_artifact",
            "source": "some_artifact_on_master",
        }
        jboss_conf = {"cli_path": "somewhere", "controller": "some_controller"}

        def list_deployments(jboss_config):
            return ["some_artifact"]

        def file_get_managed(
            name,
            template,
            source,
            source_hash,
            source_hash_name,
            user,
            group,
            mode,
            attrs,
            saltenv,
            context,
            defaults,
            skip_verify,
            kwargs,
        ):
            return "sfn", "hash", ""

        def file_manage_file(
            name,
            sfn,
            ret,
            source,
            source_sum,
            user,
            group,
            mode,
            attrs,
            saltenv,
            backup,
            makedirs,
            template,
            show_diff,
            contents,
            dir_mode,
        ):
            return {"result": True, "changes": False}

        jboss7_undeploy_mock = MagicMock()
        jboss7_deploy_mock = MagicMock()
        file_get_managed = MagicMock(side_effect=file_get_managed)
        file_manage_file = MagicMock(side_effect=file_manage_file)
        list_deployments_mock = MagicMock(side_effect=list_deployments)
        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.undeploy": jboss7_undeploy_mock,
                "jboss7.deploy": jboss7_deploy_mock,
                "file.get_managed": file_get_managed,
                "file.manage_file": file_manage_file,
                "jboss7.list_deployments": list_deployments_mock,
            },
        ):
            # when
            result = jboss7.deployed(
                name="unchanged", jboss_config=jboss_conf, salt_source=parameters
            )

            # then
            self.assertTrue(jboss7_undeploy_mock.called)
            self.assertTrue(jboss7_deploy_mock.called)

    def test_should_create_new_datasource_if_not_exists(self):
        # given
        datasource_properties = {"connection-url": "jdbc:/old-connection-url"}
        ds_status = {"created": False}

        def read_func(jboss_config, name, profile):
            if ds_status["created"]:
                return {"success": True, "result": datasource_properties}
            else:
                return {"success": False, "err_code": "JBAS014807"}

        def create_func(jboss_config, name, datasource_properties, profile):
            ds_status["created"] = True
            return {"success": True}

        read_mock = MagicMock(side_effect=read_func)
        create_mock = MagicMock(side_effect=create_func)
        update_mock = MagicMock()
        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_datasource": read_mock,
                "jboss7.create_datasource": create_mock,
                "jboss7.update_datasource": update_mock,
            },
        ):

            # when
            result = jboss7.datasource_exists(
                name="appDS",
                jboss_config={},
                datasource_properties=datasource_properties,
                profile=None,
            )

            # then
            create_mock.assert_called_with(
                name="appDS",
                jboss_config={},
                datasource_properties=datasource_properties,
                profile=None,
            )

            self.assertFalse(update_mock.called)
            self.assertEqual(result["comment"], "Datasource created.")

    def test_should_update_the_datasource_if_exists(self):
        ds_status = {"updated": False}

        def read_func(jboss_config, name, profile):
            if ds_status["updated"]:
                return {
                    "success": True,
                    "result": {"connection-url": "jdbc:/new-connection-url"},
                }
            else:
                return {
                    "success": True,
                    "result": {"connection-url": "jdbc:/old-connection-url"},
                }

        def update_func(jboss_config, name, new_properties, profile):
            ds_status["updated"] = True
            return {"success": True}

        read_mock = MagicMock(side_effect=read_func)
        create_mock = MagicMock()
        update_mock = MagicMock(side_effect=update_func)
        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_datasource": read_mock,
                "jboss7.create_datasource": create_mock,
                "jboss7.update_datasource": update_mock,
            },
        ):
            result = jboss7.datasource_exists(
                name="appDS",
                jboss_config={},
                datasource_properties={"connection-url": "jdbc:/new-connection-url"},
                profile=None,
            )

            update_mock.assert_called_with(
                name="appDS",
                jboss_config={},
                new_properties={"connection-url": "jdbc:/new-connection-url"},
                profile=None,
            )
            self.assertTrue(read_mock.called)
            self.assertEqual(result["comment"], "Datasource updated.")

    def test_should_recreate_the_datasource_if_specified(self):
        read_mock = MagicMock(
            return_value={
                "success": True,
                "result": {"connection-url": "jdbc:/same-connection-url"},
            }
        )
        create_mock = MagicMock(return_value={"success": True})
        remove_mock = MagicMock(return_value={"success": True})
        update_mock = MagicMock()
        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_datasource": read_mock,
                "jboss7.create_datasource": create_mock,
                "jboss7.remove_datasource": remove_mock,
                "jboss7.update_datasource": update_mock,
            },
        ):
            result = jboss7.datasource_exists(
                name="appDS",
                jboss_config={},
                datasource_properties={"connection-url": "jdbc:/same-connection-url"},
                recreate=True,
            )

            remove_mock.assert_called_with(name="appDS", jboss_config={}, profile=None)
            create_mock.assert_called_with(
                name="appDS",
                jboss_config={},
                datasource_properties={"connection-url": "jdbc:/same-connection-url"},
                profile=None,
            )
            self.assertEqual(result["changes"]["removed"], "appDS")
            self.assertEqual(result["changes"]["created"], "appDS")

    def test_should_inform_if_the_datasource_has_not_changed(self):
        read_mock = MagicMock(
            return_value={
                "success": True,
                "result": {"connection-url": "jdbc:/same-connection-url"},
            }
        )
        create_mock = MagicMock()
        remove_mock = MagicMock()
        update_mock = MagicMock(return_value={"success": True})

        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_datasource": read_mock,
                "jboss7.create_datasource": create_mock,
                "jboss7.remove_datasource": remove_mock,
                "jboss7.update_datasource": update_mock,
            },
        ):
            result = jboss7.datasource_exists(
                name="appDS",
                jboss_config={},
                datasource_properties={"connection-url": "jdbc:/old-connection-url"},
            )

            update_mock.assert_called_with(
                name="appDS",
                jboss_config={},
                new_properties={"connection-url": "jdbc:/old-connection-url"},
                profile=None,
            )
            self.assertFalse(create_mock.called)
            self.assertEqual(result["comment"], "Datasource not changed.")

    def test_should_create_binding_if_not_exists(self):
        # given
        binding_status = {"created": False}

        def read_func(jboss_config, binding_name, profile):
            if binding_status["created"]:
                return {"success": True, "result": {"value": "DEV"}}
            else:
                return {"success": False, "err_code": "JBAS014807"}

        def create_func(jboss_config, binding_name, value, profile):
            binding_status["created"] = True
            return {"success": True}

        read_mock = MagicMock(side_effect=read_func)
        create_mock = MagicMock(side_effect=create_func)
        update_mock = MagicMock()

        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_simple_binding": read_mock,
                "jboss7.create_simple_binding": create_mock,
                "jboss7.update_simple_binding": update_mock,
            },
        ):

            # when
            result = jboss7.bindings_exist(
                name="bindings", jboss_config={}, bindings={"env": "DEV"}, profile=None
            )

            # then
            create_mock.assert_called_with(
                jboss_config={}, binding_name="env", value="DEV", profile=None
            )
            self.assertEqual(update_mock.call_count, 0)
            self.assertEqual(result["changes"], {"added": "env:DEV\n"})
            self.assertEqual(result["comment"], "Bindings changed.")

    def test_should_update_bindings_if_exists_and_different(self):
        # given
        binding_status = {"updated": False}

        def read_func(jboss_config, binding_name, profile):
            if binding_status["updated"]:
                return {"success": True, "result": {"value": "DEV2"}}
            else:
                return {"success": True, "result": {"value": "DEV"}}

        def update_func(jboss_config, binding_name, value, profile):
            binding_status["updated"] = True
            return {"success": True}

        read_mock = MagicMock(side_effect=read_func)
        create_mock = MagicMock()
        update_mock = MagicMock(side_effect=update_func)

        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_simple_binding": read_mock,
                "jboss7.create_simple_binding": create_mock,
                "jboss7.update_simple_binding": update_mock,
            },
        ):
            # when
            result = jboss7.bindings_exist(
                name="bindings", jboss_config={}, bindings={"env": "DEV2"}, profile=None
            )

            # then
            update_mock.assert_called_with(
                jboss_config={}, binding_name="env", value="DEV2", profile=None
            )
            self.assertEqual(create_mock.call_count, 0)
            self.assertEqual(result["changes"], {"changed": "env:DEV->DEV2\n"})
            self.assertEqual(result["comment"], "Bindings changed.")

    def test_should_not_update_bindings_if_same(self):
        # given
        read_mock = MagicMock(
            return_value={"success": True, "result": {"value": "DEV2"}}
        )
        create_mock = MagicMock()
        update_mock = MagicMock()

        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_simple_binding": read_mock,
                "jboss7.create_simple_binding": create_mock,
                "jboss7.update_simple_binding": update_mock,
            },
        ):
            # when
            result = jboss7.bindings_exist(
                name="bindings", jboss_config={}, bindings={"env": "DEV2"}
            )

            # then
            self.assertEqual(create_mock.call_count, 0)
            self.assertEqual(update_mock.call_count, 0)
            self.assertEqual(result["changes"], {})
            self.assertEqual(result["comment"], "Bindings not changed.")

    def test_should_raise_exception_if_cannot_create_binding(self):
        def read_func(jboss_config, binding_name, profile):
            return {"success": False, "err_code": "JBAS014807"}

        def create_func(jboss_config, binding_name, value, profile):
            return {"success": False, "failure-description": "Incorrect binding name."}

        read_mock = MagicMock(side_effect=read_func)
        create_mock = MagicMock(side_effect=create_func)
        update_mock = MagicMock()

        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_simple_binding": read_mock,
                "jboss7.create_simple_binding": create_mock,
                "jboss7.update_simple_binding": update_mock,
            },
        ):
            # when
            try:
                jboss7.bindings_exist(
                    name="bindings",
                    jboss_config={},
                    bindings={"env": "DEV2"},
                    profile=None,
                )
                self.fail("An exception should be thrown")
            except CommandExecutionError as e:
                self.assertEqual(six.text_type(e), "Incorrect binding name.")

    def test_should_raise_exception_if_cannot_update_binding(self):
        def read_func(jboss_config, binding_name, profile):
            return {"success": True, "result": {"value": "DEV"}}

        def update_func(jboss_config, binding_name, value, profile):
            return {"success": False, "failure-description": "Incorrect binding name."}

        read_mock = MagicMock(side_effect=read_func)
        create_mock = MagicMock()
        update_mock = MagicMock(side_effect=update_func)

        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_simple_binding": read_mock,
                "jboss7.create_simple_binding": create_mock,
                "jboss7.update_simple_binding": update_mock,
            },
        ):

            # when
            try:
                jboss7.bindings_exist(
                    name="bindings",
                    jboss_config={},
                    bindings={"env": "!@#!///some weird value"},
                    profile=None,
                )
                self.fail("An exception should be thrown")
            except CommandExecutionError as e:
                self.assertEqual(six.text_type(e), "Incorrect binding name.")

    def test_datasource_exist_create_datasource_good_code(self):
        jboss_config = {
            "cli_path": "/home/ch44d/Desktop/wildfly-18.0.0.Final/bin/jboss-cli.sh",
            "controller": "127.0.0.1: 9990",
            "cli_user": "user",
            "cli_password": "user",
        }

        datasource_properties = {
            "driver - name": "h2",
            "connection - url": "jdbc:sqlserver://127.0.0.1:1433;DatabaseName=test_s2",
            "jndi - name": "java:/home/ch44d/Desktop/sqljdbc_7.4/enu/mssql-jdbc-7.4.1.jre8.jar",
            "user - name": "user",
            "password": "user",
            "use - java - context": True,
        }

        read_datasource = MagicMock(
            return_value={"success": False, "err_code": "WFLYCTL0216"}
        )

        error_msg = "Error: -1"
        create_datasource = MagicMock(
            return_value={"success": False, "stdout": error_msg}
        )

        with patch.dict(
            jboss7.__salt__,
            {
                "jboss7.read_datasource": read_datasource,
                "jboss7.create_datasource": create_datasource,
            },
        ):
            ret = jboss7.datasource_exists("SQL", jboss_config, datasource_properties)

            self.assertTrue("result" in ret)
            self.assertFalse(ret["result"])
            self.assertTrue("comment" in ret)
            self.assertTrue(error_msg in ret["comment"])

            read_datasource.assert_called_once()
            create_datasource.assert_called_once()

    def test_datasource_exist_create_datasource_bad_code(self):
        jboss_config = {
            "cli_path": "/home/ch44d/Desktop/wildfly-18.0.0.Final/bin/jboss-cli.sh",
            "controller": "127.0.0.1: 9990",
            "cli_user": "user",
            "cli_password": "user",
        }

        datasource_properties = {
            "driver - name": "h2",
            "connection - url": "jdbc:sqlserver://127.0.0.1:1433;DatabaseName=test_s2",
            "jndi - name": "java:/home/ch44d/Desktop/sqljdbc_7.4/enu/mssql-jdbc-7.4.1.jre8.jar",
            "user - name": "user",
            "password": "user",
            "use - java - context": True,
        }

        read_datasource = MagicMock(
            return_value={
                "success": False,
                "err_code": "WFLYCTL0217",
                "failure-description": "Something happened",
            }
        )

        with patch.dict(jboss7.__salt__, {"jboss7.read_datasource": read_datasource}):
            self.assertRaises(
                CommandExecutionError,
                jboss7.datasource_exists,
                "SQL",
                jboss_config,
                datasource_properties,
            )
            read_datasource.assert_called_once()

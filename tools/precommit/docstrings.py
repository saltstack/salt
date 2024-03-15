"""
Check salt code base for for missing or wrong docstrings.
"""

# Skip mypy checks since it will follow into Salt which doesn't yet have proper types defined
# mypy: ignore-errors
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
import sys
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.utils
from tools.precommit import SALT_INTERNAL_LOADERS_PATHS

SALT_CODE_DIR = tools.utils.REPO_ROOT / "salt"
SALT_MODULES_PATH = SALT_CODE_DIR / "modules"
THIS_FILE = pathlib.Path(__file__).relative_to(tools.utils.REPO_ROOT)

MISSING_DOCSTRINGS = {
    "salt/auth/django.py": ["is_connection_usable"],
    "salt/auth/rest.py": ["rest_auth_setup"],
    "salt/auth/yubico.py": ["groups"],
    "salt/beacons/inotify.py": ["close"],
    "salt/beacons/junos_rre_keys.py": ["beacon"],
    "salt/beacons/salt_monitor.py": ["validate", "beacon"],
    "salt/beacons/watchdog.py": ["close", "to_salt_event"],
    "salt/cache/localfs.py": ["get_storage_id", "init_kwargs"],
    "salt/cloud/clouds/clc.py": [
        "get_creds",
        "get_configured_provider",
        "get_queue_data",
    ],
    "salt/cloud/clouds/ec2.py": ["query", "sign"],
    "salt/cloud/clouds/libvirt.py": [
        "get_domain_ips",
        "destroy_domain",
        "create_volume_with_backing_store_xml",
        "generate_new_name",
        "find_pool_and_volume",
        "to_ip_addr_type",
        "get_domain_ip",
        "get_domain_volumes",
        "create_volume_xml",
    ],
    "salt/cloud/clouds/lxc.py": [
        "avail_images",
        "list_nodes_full",
        "list_nodes",
        "get_provider",
    ],
    "salt/cloud/clouds/packet.py": ["get_devices_by_token", "is_profile_configured"],
    "salt/cloud/clouds/profitbricks.py": ["signal_event"],
    "salt/cloud/clouds/pyrax.py": [
        "queues_exists",
        "queues_show",
        "queues_delete",
        "queues_create",
    ],
    "salt/engines/junos_syslog.py": ["start"],
    "salt/engines/logentries.py": ["event_bus_context"],
    "salt/engines/logstash_engine.py": ["event_bus_context"],
    "salt/engines/reactor.py": ["start"],
    "salt/engines/redis_sentinel.py": ["start"],
    "salt/engines/test.py": ["event_bus_context"],
    "salt/grains/chronos.py": ["os_family", "os_data", "kernel", "os"],
    "salt/grains/cimc.py": ["cimc"],
    "salt/grains/esxi.py": ["os_family", "kernel", "os", "esxi"],
    "salt/grains/fx2.py": ["kernel", "os_family", "fx2", "location", "os_data"],
    "salt/grains/junos.py": ["facts", "os_family", "defaults"],
    "salt/grains/marathon.py": ["kernel", "os", "os_family", "os_data", "marathon"],
    "salt/grains/metadata.py": ["metadata"],
    "salt/grains/nxos.py": ["system_information"],
    "salt/grains/panos.py": ["panos"],
    "salt/grains/philips_hue.py": ["vendor", "kernel", "os", "os_family", "product"],
    "salt/grains/rest_sample.py": ["kernel", "os", "os_family", "location", "os_data"],
    "salt/grains/ssh_sample.py": ["location", "os_data", "kernel"],
    "salt/log_handlers/fluent_mod.py": ["setup", "setup_handlers", "get_global_sender"],
    "salt/log_handlers/log4mongo_mod.py": ["setup_handlers"],
    "salt/log_handlers/logstash_mod.py": ["setup_handlers"],
    "salt/modules/chassis.py": ["chassis_credentials", "cmd"],
    "salt/modules/csf.py": [
        "disable_testing_mode",
        "skip_nic",
        "get_testing_status",
        "build_directions",
        "get_option",
        "enable_testing_mode",
        "remove_temp_rule",
        "get_skipped_nics",
        "set_option",
        "remove_rule",
        "split_option",
        "skip_nics",
    ],
    "salt/modules/dracr.py": [
        "get_general",
        "set_dns_dracname",
        "set_nicvlan",
        "get_dns_dracname",
        "bare_rac_cmd",
        "set_general",
        "inventory",
        "set_niccfg",
    ],
    "salt/modules/dummyproxy_pkg.py": [
        "remove",
        "installed",
        "install",
        "list_pkgs",
        "upgrade",
    ],
    "salt/modules/esxcluster.py": ["get_details"],
    "salt/modules/esxdatacenter.py": ["get_details"],
    "salt/modules/esxi.py": ["cmd", "get_details"],
    "salt/modules/esxvm.py": ["get_details"],
    "salt/modules/powerpath.py": ["has_powerpath"],
    "salt/modules/rest_pkg.py": [
        "remove",
        "installed",
        "install",
        "list_pkgs",
        "upgrade",
    ],
    "salt/modules/ssh_pkg.py": ["install", "list_pkgs", "remove"],
    "salt/modules/swift.py": ["head"],
    "salt/modules/sysbench.py": ["ping"],
    "salt/modules/test.py": ["missing_func"],
    "salt/modules/test_virtual.py": ["ping"],
    "salt/modules/vcenter.py": ["get_details"],
    "salt/netapi/rest_tornado/__init__.py": ["get_application"],
    "salt/output/__init__.py": ["progress_end"],
    "salt/pillar/extra_minion_data_in_pillar.py": ["ext_pillar"],
    "salt/pillar/gpg.py": ["ext_pillar"],
    "salt/pillar/makostack.py": ["ext_pillar"],
    "salt/pillar/nacl.py": ["ext_pillar"],
    "salt/proxy/cisconso.py": ["init"],
    "salt/proxy/esxi.py": ["is_connected_via_vcenter"],
    "salt/proxy/fx2.py": ["host"],
    "salt/proxy/junos.py": [
        "reboot_active",
        "conn",
        "get_reboot_active",
        "initialized",
        "reboot_clear",
        "get_serialized_facts",
    ],
    "salt/proxy/netmiko_px.py": ["connection", "make_con"],
    "salt/proxy/rest_sample.py": ["init", "alive", "fns", "fix_outage"],
    "salt/queues/pgjsonb_queue.py": ["handle_queue_creation"],
    "salt/renderers/pydsl.py": ["render"],
    "salt/renderers/pyobjects.py": ["render"],
    "salt/renderers/stateconf.py": [
        "add_goal_state",
        "rewrite_sls_includes_excludes",
        "add_implicit_requires",
        "add_start_state",
        "extract_state_confs",
        "rename_state_ids",
        "has_names_decls",
        "statelist",
        "render",
    ],
    "salt/returners/zabbix_return.py": ["returner", "zbx", "zabbix_send"],
    "salt/roster/range.py": ["target_glob", "target_range"],
    "salt/sdb/consul.py": ["set_", "get"],
    "salt/states/apache.py": ["configfile"],
    "salt/states/boto_elasticache.py": [
        "replication_group_present",
        "cache_cluster_present",
        "replication_group_absent",
        "subnet_group_absent",
        "cache_cluster_absent",
    ],
    "salt/states/boto_rds.py": ["subnet_group_absent"],
    "salt/states/boto_route53.py": ["rr_absent", "rr_present"],
    "salt/states/boto_vpc.py": ["vpc_peering_connection_absent"],
    "salt/states/cmd.py": ["wait_call"],
    "salt/states/esxdatacenter.py": ["mod_init"],
    "salt/states/junos.py": ["resultdecorator"],
    "salt/states/keystone_role_grant.py": ["present", "absent"],
    "salt/states/libcloud_dns.py": ["state_result"],
    "salt/states/libcloud_loadbalancer.py": ["state_result"],
    "salt/states/libcloud_storage.py": ["state_result"],
    "salt/states/pkgng.py": ["update_packaging_site"],
    "salt/utils/aws.py": ["assumed_creds"],
    "salt/utils/boto3mod.py": ["exactly_one", "get_error", "ordered"],
    "salt/utils/boto_elb_tag.py": ["get_tag_descriptions"],
    "salt/utils/botomod.py": ["exactly_one", "get_error"],
    "salt/utils/dictdiffer.py": ["diff", "deep_diff"],
    "salt/utils/dictupdate.py": [
        "merge",
        "merge_recurse",
        "merge_overwrite",
        "merge_list",
        "merge_aggregate",
    ],
    "salt/utils/dockermod/__init__.py": ["get_client_args"],
    "salt/utils/dockermod/translate/container.py": [
        "ipc_mode",
        "volumes_from",
        "cpu_period",
        "network_mode",
        "domainname",
        "stop_signal",
        "cpuset_mems",
        "command",
        "memswap_limit",
        "pid_mode",
        "pids_limit",
        "security_opt",
        "network_disabled",
        "labels",
        "sysctls",
        "log_driver",
        "userns_mode",
        "cpuset_cpus",
        "lxc_conf",
        "environment",
        "read_only",
        "oom_score_adj",
        "device_write_iops",
        "mem_swappiness",
        "isolation",
        "blkio_weight",
        "entrypoint",
        "hostname",
        "dns_opt",
        "mac_address",
        "cpu_shares",
        "privileged",
        "stdin_open",
        "dns",
        "publish_all_ports",
        "mem_limit",
        "log_opt",
        "devices",
        "auto_remove",
        "cap_add",
        "group_add",
        "stop_timeout",
        "oom_kill_disable",
        "tty",
        "detach",
        "storage_opt",
        "shm_size",
        "name",
        "host_config",
        "device_read_bps",
        "cpu_group",
        "device_read_iops",
        "dns_search",
        "links",
        "volume_driver",
        "extra_hosts",
        "tmpfs",
        "ulimits",
        "cap_drop",
        "device_write_bps",
    ],
    "salt/utils/dockermod/translate/helpers.py": [
        "validate_subnet",
        "translate_str",
        "validate_ip",
        "translate_bool",
        "split",
        "translate_int",
    ],
    "salt/utils/dockermod/translate/network.py": [
        "attachable",
        "subnet",
        "driver",
        "ipam_opts",
        "aux_addresses",
        "ingress",
        "ipam_driver",
        "ipam_pools",
        "iprange",
        "gateway",
        "enable_ipv6",
        "internal",
        "check_duplicate",
        "options",
        "ipam",
        "labels",
    ],
    "salt/utils/entrypoints.py": [
        "name_and_version_from_entry_point",
        "iter_entry_points",
    ],
    "salt/utils/error.py": ["pack_exception"],
    "salt/utils/find.py": ["path_depth"],
    "salt/utils/gzip_util.py": ["open_fileobj", "uncompress", "open"],
    "salt/utils/icinga2.py": ["get_certs_path"],
    "salt/utils/jinja.py": [
        "jinja_raise",
        "method_call",
        "show_full_context",
        "regex_escape",
    ],
    "salt/utils/listdiffer.py": ["list_diff"],
    "salt/utils/namecheap.py": [
        "atts_to_dict",
        "get_opts",
        "post_request",
        "string_to_value",
        "xml_to_dict",
        "get_request",
    ],
    "salt/utils/nxos.py": ["version_info"],
    "salt/utils/openstack/neutron.py": [
        "check_keystone",
        "check_neutron",
        "sanitize_neutronclient",
    ],
    "salt/utils/openstack/nova.py": [
        "sanatize_novaclient",
        "get_entry",
        "get_endpoint_url_v3",
        "get_entry_multi",
        "check_nova",
    ],
    "salt/utils/openstack/swift.py": ["mkdirs", "check_swift"],
    "salt/utils/pkg/__init__.py": ["split_comparison"],
    "salt/utils/profile.py": ["activate_profile", "output_profile"],
    "salt/utils/pyobjects.py": ["need_salt"],
    "salt/utils/reclass.py": [
        "set_inventory_base_uri_default",
        "filter_out_source_path_option",
        "prepend_reclass_source_path",
    ],
    "salt/utils/roster_matcher.py": ["targets"],
    "salt/utils/saltclass.py": [
        "find_and_process_re",
        "get_tops",
        "render_yaml",
        "get_env_from_dict",
        "get_pillars",
        "expand_variables",
        "render_jinja",
        "expand_classes_in_order",
        "dict_search_and_replace",
        "expanded_dict_from_minion",
        "find_value_to_expand",
        "dict_merge",
        "get_class",
    ],
    "salt/utils/smb.py": ["mkdirs", "delete_file", "delete_directory"],
    "salt/utils/ssh.py": ["key_is_encrypted"],
    "salt/utils/stringio.py": ["is_writable", "is_stringio", "is_readable"],
    "salt/utils/stringutils.py": ["random"],
    "salt/utils/virtualbox.py": [
        "machine_get_machinestate_str",
        "machine_get_machinestate_tuple",
    ],
    "salt/utils/win_osinfo.py": ["get_os_version_info"],
    "salt/utils/win_runas.py": ["split_username"],
    "salt/utils/yamldumper.py": [
        "represent_undefined",
        "represent_ordereddict",
        "get_dumper",
    ],
    "salt/utils/yamlloader.py": ["load"],
    "salt/utils/yamlloader_old.py": ["load"],
}
MISSING_EXAMPLES = {
    "salt/modules/acme.py": ["has", "renew_by", "needs_renewal"],
    "salt/modules/apkpkg.py": ["purge"],
    "salt/modules/arista_pyeapi.py": ["get_connection"],
    "salt/modules/artifactory.py": [
        "get_latest_release",
        "get_latest_snapshot",
        "get_release",
        "get_snapshot",
    ],
    "salt/modules/bigip.py": ["delete_pool"],
    "salt/modules/boto3_elasticache.py": [
        "delete_cache_cluster",
        "describe_cache_subnet_groups",
        "create_cache_parameter_group",
        "describe_replication_groups",
        "cache_security_group_exists",
        "add_tags_to_resource",
        "authorize_cache_security_group_ingress",
        "modify_cache_cluster",
        "cache_subnet_group_exists",
        "describe_cache_clusters",
        "cache_cluster_exists",
        "delete_cache_security_group",
        "describe_cache_parameter_groups",
        "copy_snapshot",
        "delete_cache_parameter_group",
        "delete_cache_subnet_group",
        "describe_cache_security_groups",
        "create_cache_cluster",
        "list_tags_for_resource",
        "revoke_cache_security_group_ingress",
        "modify_cache_subnet_group",
        "replication_group_exists",
        "remove_tags_from_resource",
        "create_replication_group",
        "modify_replication_group",
        "create_cache_subnet_group",
        "create_cache_security_group",
        "delete_replication_group",
        "list_cache_subnet_groups",
    ],
    "salt/modules/boto3_elasticsearch.py": [
        "delete_elasticsearch_domain",
        "describe_elasticsearch_domain",
        "describe_reserved_elasticsearch_instances",
        "wait_for_upgrade",
        "start_elasticsearch_service_software_update",
        "cancel_elasticsearch_service_software_update",
        "list_domain_names",
        "exists",
        "describe_reserved_elasticsearch_instance_offerings",
        "list_elasticsearch_instance_types",
        "list_tags",
        "delete_elasticsearch_service_role",
        "get_upgrade_status",
        "get_upgrade_history",
        "get_compatible_elasticsearch_versions",
        "purchase_reserved_elasticsearch_instance_offering",
        "describe_elasticsearch_domain_config",
        "list_elasticsearch_versions",
    ],
    "salt/modules/boto3_route53.py": ["aws_encode"],
    "salt/modules/boto_cloudwatch.py": ["delete_alarm"],
    "salt/modules/boto_ec2.py": ["set_volumes_tags"],
    "salt/modules/boto_elasticache.py": ["create_subnet_group"],
    "salt/modules/boto_elb.py": [
        "set_health_check",
        "set_attributes",
        "create",
        "delete",
    ],
    "salt/modules/boto_rds.py": [
        "create_read_replica",
        "describe_parameters",
        "create_parameter_group",
        "modify_db_instance",
        "create_subnet_group",
        "create_option_group",
        "create",
        "describe_parameter_group",
    ],
    "salt/modules/boto_sns.py": [
        "get_all_subscriptions_by_topic",
        "create",
        "subscribe",
        "delete",
    ],
    "salt/modules/boto_ssm.py": ["get_parameter", "delete_parameter", "put_parameter"],
    "salt/modules/capirca_acl.py": ["get_filter_pillar", "get_term_pillar"],
    "salt/modules/ceph.py": ["zap"],
    "salt/modules/ciscoconfparse_mod.py": [
        "find_objects",
        "find_objects_wo_child",
        "find_objects_w_child",
    ],
    "salt/modules/cisconso.py": [
        "get_data",
        "get_rollbacks",
        "get_rollback",
        "info",
        "set_data_value",
        "apply_rollback",
    ],
    "salt/modules/cryptdev.py": ["active"],
    "salt/modules/datadog_api.py": ["post_event"],
    "salt/modules/defaults.py": ["deepcopy", "update"],
    "salt/modules/dracr.py": ["update_firmware", "update_firmware_nfs_or_cifs"],
    "salt/modules/dummyproxy_service.py": ["enabled", "running"],
    "salt/modules/ebuildpkg.py": ["porttree_matches"],
    "salt/modules/eselect.py": ["exec_action", "set_target", "get_current_target"],
    "salt/modules/freebsd_update.py": [
        "update",
        "ids",
        "rollback",
        "install",
        "fetch",
        "upgrade",
    ],
    "salt/modules/glanceng.py": [
        "setup_clouds",
        "get_openstack_cloud",
        "get_operator_cloud",
        "compare_changes",
    ],
    "salt/modules/glassfish.py": [
        "delete_jdbc_connection_pool",
        "create_connector_c_pool",
        "delete_jdbc_resource",
        "create_connector_resource",
        "enum_jdbc_connection_pool",
        "enum_connector_c_pool",
        "enum_jdbc_resource",
        "enum_admin_object_resource",
        "get_system_properties",
        "get_jdbc_connection_pool",
        "delete_system_properties",
        "delete_connector_c_pool",
        "create_jdbc_connection_pool",
        "update_jdbc_connection_pool",
        "update_system_properties",
        "update_connector_c_pool",
        "create_admin_object_resource",
        "enum_connector_resource",
        "create_jdbc_resource",
        "update_connector_resource",
        "delete_connector_resource",
        "delete_admin_object_resource",
        "update_admin_object_resource",
        "update_jdbc_resource",
        "get_admin_object_resource",
        "get_connector_resource",
        "get_connector_c_pool",
        "get_jdbc_resource",
    ],
    "salt/modules/google_chat.py": ["send_message"],
    "salt/modules/hadoop.py": ["namenode_format"],
    "salt/modules/highstate_doc.py": [
        "processor_markdown",
        "read_file",
        "process_lowstates",
        "markdown_full_jinja_template",
        "markdown_default_jinja_template",
        "render",
        "markdown_basic_jinja_template",
    ],
    "salt/modules/ifttt.py": ["trigger_event"],
    "salt/modules/influxdbmod.py": ["query", "revoke_privilege", "grant_privilege"],
    "salt/modules/infoblox.py": ["diff_objects"],
    "salt/modules/kapacitor.py": ["version"],
    "salt/modules/keystoneng.py": [
        "get_openstack_cloud",
        "compare_changes",
        "get_operator_cloud",
        "setup_clouds",
        "get_entity",
    ],
    "salt/modules/kubernetesmod.py": [
        "replace_service",
        "create_deployment",
        "create_service",
        "create_pod",
        "replace_deployment",
    ],
    "salt/modules/logmod.py": [
        "warning",
        "critical",
        "info",
        "exception",
        "error",
        "debug",
    ],
    "salt/modules/lxc.py": ["create"],
    "salt/modules/lxd.py": [
        "pylxd_save_object",
        "container_start",
        "container_delete",
        "container_freeze",
        "container_unfreeze",
        "container_device_delete",
        "pylxd_client_get",
        "container_config_get",
        "container_restart",
        "container_rename",
        "container_device_get",
        "container_device_add",
        "container_config_delete",
        "container_stop",
        "container_get",
        "sync_config_devices",
        "container_file_get",
        "container_state",
        "container_config_set",
    ],
    "salt/modules/nacl.py": ["enc", "dec"],
    "salt/modules/nagios.py": ["run_all", "retcode"],
    "salt/modules/napalm_formula.py": ["dictupdate"],
    "salt/modules/napalm_mod.py": ["netmiko_conn", "pyeapi_conn"],
    "salt/modules/napalm_netacl.py": ["get_filter_pillar", "get_term_pillar"],
    "salt/modules/napalm_probes.py": ["delete_probes", "schedule_probes", "set_probes"],
    "salt/modules/netbox.py": ["get_", "filter_", "slugify"],
    "salt/modules/netmiko_mod.py": ["call", "multi_call", "get_connection"],
    "salt/modules/neutronng.py": [
        "get_openstack_cloud",
        "compare_changes",
        "get_operator_cloud",
        "subnet_update",
        "setup_clouds",
    ],
    "salt/modules/nexus.py": [
        "get_latest_release",
        "get_latest_snapshot",
        "get_release",
        "get_snapshot_version_string",
        "get_snapshot",
    ],
    "salt/modules/nix.py": [
        "collect_garbage",
        "uninstall",
        "list_pkgs",
        "install",
        "upgrade",
    ],
    "salt/modules/nspawn.py": ["stop", "restart"],
    "salt/modules/nxos.py": [
        "set_role",
        "get_user",
        "find",
        "cmd",
        "get_roles",
        "show_run",
        "grains",
        "save_running_config",
        "remove_user",
        "check_role",
        "grains_refresh",
        "add_config",
        "system_info",
        "sendline",
        "delete_config",
        "show_ver",
        "check_password",
        "set_password",
        "ping",
        "unset_role",
        "replace",
    ],
    "salt/modules/nxos_upgrade.py": ["upgrade", "check_upgrade_impact"],
    "salt/modules/openbsdpkg.py": ["install"],
    "salt/modules/opkg.py": ["version_clean", "check_extra_requirements"],
    "salt/modules/pagerduty_util.py": [
        "create_or_update_resource",
        "resource_absent",
        "resource_present",
        "get_resource",
        "delete_resource",
    ],
    "salt/modules/parallels.py": [
        "delete",
        "exists",
        "list_vms",
        "status",
        "revert_snapshot",
        "stop",
        "prlsrvctl",
        "clone",
        "snapshot",
        "reset",
        "restart",
        "delete_snapshot",
        "exec_",
        "prlctl",
        "list_snapshots",
        "start",
    ],
    "salt/modules/pcs.py": ["item_create", "item_show"],
    "salt/modules/pkg_resource.py": ["format_pkg_list", "format_version"],
    "salt/modules/pkgin.py": ["normalize_name"],
    "salt/modules/portage_config.py": [
        "get_all_cpv_use",
        "is_changed_uses",
        "get_installed_use",
        "filter_flags",
        "get_iuse",
        "get_cleared_flags",
    ],
    "salt/modules/poudriere.py": ["create_ports_tree"],
    "salt/modules/powerpath.py": ["add_license", "list_licenses", "remove_license"],
    "salt/modules/ps.py": ["pkill", "kill_pid", "pgrep"],
    "salt/modules/rest_service.py": ["enabled", "running"],
    "salt/modules/runit.py": [
        "get_svc_alias",
        "get_svc_avail_path",
        "add_svc_avail_path",
    ],
    "salt/modules/s3.py": ["put", "get", "delete"],
    "salt/modules/saltcheck.py": ["parallel_scheck"],
    "salt/modules/selinux.py": ["filetype_id_to_string"],
    "salt/modules/sensehat.py": [
        "get_pressure",
        "get_temperature_from_humidity",
        "get_pixels",
        "get_temperature",
        "set_pixels",
        "get_pixel",
        "get_humidity",
        "get_temperature_from_pressure",
    ],
    "salt/modules/sensors.py": ["sense"],
    "salt/modules/slsutil.py": ["banner", "boolstr"],
    "salt/modules/smartos_imgadm.py": ["docker_to_uuid"],
    "salt/modules/ssh_service.py": ["enabled", "running"],
    "salt/modules/state.py": ["test", "get_pauses", "apply_"],
    "salt/modules/swift.py": ["put", "get", "delete"],
    "salt/modules/test.py": ["rand_str", "try_"],
    "salt/modules/tls.py": ["validate"],
    "salt/modules/tomcat.py": ["extract_war_version"],
    "salt/modules/trafficserver.py": [
        "refresh",
        "set_config",
        "startup",
        "read_metric",
        "shutdown",
        "bounce_local",
        "alarms",
        "clear_node",
        "bounce_cluster",
        "status",
        "match_config",
        "offline",
        "zero_cluster",
        "zero_node",
        "restart_local",
        "read_config",
        "clear_alarms",
        "clear_cluster",
        "restart_cluster",
        "match_metric",
    ],
    "salt/modules/vagrant.py": ["get_machine_id", "get_vm_info"],
    "salt/modules/virt.py": [
        "nesthash",
        "pool_update",
        "init",
        "node_devices",
        "network_update",
    ],
    "salt/modules/virtualenv_mod.py": ["virtualenv_ver"],
    "salt/modules/vsphere.py": [
        "update_vm",
        "set_advanced_configs",
        "register_vm",
        "get_vm_config",
        "get_vm_config_file",
        "compare_vm_configs",
        "get_advanced_configs",
        "delete_advanced_configs",
        "get_vm",
    ],
    "salt/modules/win_pkg.py": ["get_package_info"],
    "salt/modules/win_timezone.py": ["zone_compare"],
    "salt/modules/zk_concurrency.py": [
        "lock",
        "party_members",
        "unlock",
        "lock_holders",
    ],
}

SUMMARY = """\
### Hi! I'm your friendly PR bot!

You might be wondering what I'm doing commenting here on your PR.

**Yes, as a matter of fact, I am...**

I'm just here to help us improve the documentation. I can't respond to
questions or anything, but what I *can* do, I do well!

**Okay... so what do you do?**

I detect modules that are missing docstrings or "CLI Example" on existing docstrings!
When I was created we had a *lot* of these. The documentation for these
modules need some love and attention to make Salt better for our users.

**So what does that have to do with my PR?**

I noticed that in this PR there are some files changed that have some of these
issues. So I'm leaving this comment to let you know your options.

**Okay, what are they?**

Well, my favorite, is that since you were making changes here I'm hoping that
you would be the most familiar with this module and be able to add some other
examples or fix any of the reported issues.

**If I can, then what?**

Well, you can either add them to this PR or add them to another PR. Either way is fine!

**Well... what if I can't, or don't want to?**

That's also fine! We appreciate *all* contributions to the Salt Project. If you
can't add those other examples, either because you're too busy, or unfamiliar,
or you just aren't interested, we still appreciate the contributions that
you've made already.

Whatever approach you decide to take, just drop a comment in the PR letting us know!
"""

cgroup = command_group(name="docstrings", help=__doc__, parent="pre-commit")


def annotate(
    ctx: Context,
    kind: str,
    fpath: pathlib.Path,
    start_lineno: int,
    end_lineno: int,
    message: str,
) -> None:
    if kind not in ("warning", "error"):
        raise RuntimeError("The annotation kind can only be one of 'warning', 'error'.")
    if os.environ.get("GH_ACTIONS_ANNOTATE") is None:
        return

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set. Not adding annotations.")
        return

    if TYPE_CHECKING:
        assert github_output is not None

    message = (
        message.rstrip().replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    )
    # Print it to stdout so that the GitHub runner pick's it up and adds the annotation
    ctx.print(
        f"::{kind} file={fpath},line={start_lineno},endLine={end_lineno}::{message}",
        soft_wrap=True,
    )


@cgroup.command(
    name="check",
    arguments={
        "files": {
            "help": "List of files to check",
            "nargs": "*",
        },
        "suppress_warnings": {
            "help": "Supress warning messages on known issues",
        },
        "check_proper_formatting": {
            "help": "Run formatting checks on docstrings",
        },
        "error_on_known_failures": {
            "help": "Raise an error on known failures",
        },
    },
)
def check_docstrings(
    ctx: Context,
    files: list[pathlib.Path],
    suppress_warnings: bool = False,
    check_proper_formatting: bool = False,
    error_on_known_failures: bool = False,
) -> None:
    """
    Check salt's docstrings
    """
    if not files:
        _files = list(SALT_CODE_DIR.rglob("*.py"))
    else:
        _files = [fpath.resolve() for fpath in files if fpath.suffix == ".py"]

    errors = 0
    exitcode = 0
    warnings = 0
    for path in _files:
        if str(path).startswith(str(tools.utils.REPO_ROOT / "salt" / "ext")):
            continue
        contents = path.read_text()
        try:
            module = ast.parse(path.read_text(), filename=str(path))
            module_docstring = ast.get_docstring(module, clean=False)
            if module_docstring:
                error = _check_valid_versions_on_docstrings(module_docstring)
                if error:
                    errors += 1
                    exitcode = 1
                    ctx.error(
                        "The module '{}' does not provide a proper `{}` version: {!r} is not valid.".format(
                            path.relative_to(tools.utils.REPO_ROOT),
                            *error,
                        )
                    )

            for funcdef in [
                node for node in module.body if isinstance(node, ast.FunctionDef)
            ]:
                docstring = ast.get_docstring(funcdef, clean=False)
                if docstring:
                    error = _check_valid_versions_on_docstrings(docstring)
                    if error:
                        errors += 1
                        exitcode = 1
                        ctx.error(
                            "The module '{}' does not provide a proper `{}` version: {!r} is not valid.".format(
                                path,
                                *error,
                            )
                        )
                        annotate(
                            ctx,
                            "error",
                            path,
                            funcdef.lineno,
                            funcdef.body[0].lineno,
                            "Version {1!r} is not valid for {0!r}".format(*error),
                        )

                if not str(path).startswith(SALT_INTERNAL_LOADERS_PATHS):
                    # No further docstrings checks are needed
                    continue

                funcname = funcdef.name
                relpath = str(path.relative_to(tools.utils.REPO_ROOT))

                # We're dealing with a salt loader module
                if funcname.startswith("_"):
                    # We're not interested in internal functions
                    continue

                if not docstring:
                    if (
                        funcname in MISSING_DOCSTRINGS.get(relpath, ())
                        and error_on_known_failures is False
                    ):
                        warnings += 1
                        if suppress_warnings is False:
                            ctx.warn(
                                f"The function '{funcname}' on '{relpath}' does not have a docstring"
                            )
                        annotate(
                            ctx,
                            "warning",
                            path.relative_to(tools.utils.REPO_ROOT),
                            funcdef.lineno,
                            funcdef.body[0].lineno,
                            "Missing docstring",
                        )
                        continue
                    errors += 1
                    exitcode = 1
                    ctx.error(
                        f"The function '{funcname}' on '{relpath}' does not have a docstring"
                    )
                    annotate(
                        ctx,
                        "error",
                        path.relative_to(tools.utils.REPO_ROOT),
                        funcdef.lineno,
                        funcdef.body[0].lineno,
                        "Missing docstring",
                    )
                    continue
                elif funcname in MISSING_DOCSTRINGS.get(relpath, ()):
                    # This was previously a know function with a missing docstring.
                    # Warn about it so that it get's removed from this list
                    errors += 1
                    exitcode = 1
                    ctx.error(
                        f"The function '{funcname}' on '{relpath}' was previously known to not "
                        "have a docstring, which is no longer the case. Please remove it from "
                        f"'MISSING_DOCSTRINGS' in '{THIS_FILE}'"
                    )

                try:
                    salt_modules_relpath = path.relative_to(SALT_MODULES_PATH)
                    if str(salt_modules_relpath.parent) != ".":
                        # We don't want to check nested packages
                        continue
                    # But this is a module under salt/modules, let's check
                    # the CLI examples
                except ValueError:
                    # We're not checking CLI examples in any other salt loader modules
                    continue

                if _check_cli_example_present(docstring) is False:
                    if (
                        funcname in MISSING_EXAMPLES.get(relpath, ())
                        and error_on_known_failures is False
                    ):
                        warnings += 1
                        if suppress_warnings is False:
                            ctx.warn(
                                f"The function '{funcname}' on '{relpath}' does not have a "
                                "'CLI Example:' in its docstring"
                            )
                        annotate(
                            ctx,
                            "warning",
                            path.relative_to(tools.utils.REPO_ROOT),
                            funcdef.lineno,
                            funcdef.body[0].lineno,
                            "Missing 'CLI Example:' in docstring",
                        )
                        continue
                    errors += 1
                    exitcode = 1
                    ctx.error(
                        f"The function '{funcname}' on '{relpath}' does not have a 'CLI Example:' in its docstring"
                    )
                    annotate(
                        ctx,
                        "error",
                        path.relative_to(tools.utils.REPO_ROOT),
                        funcdef.lineno,
                        funcdef.body[0].lineno,
                        "Missing 'CLI Example:' in docstring",
                    )
                    continue
                elif funcname in MISSING_EXAMPLES.get(relpath, ()):
                    # This was previously a know function with a missing CLI example
                    # Warn about it so that it get's removed from this list
                    errors += 1
                    exitcode = 1
                    ctx.error(
                        f"The function '{funcname}' on '{relpath}' was previously known to not "
                        "have a CLI Example, which is no longer the case. Please remove it from "
                        f"'MISSING_EXAMPLES' in '{THIS_FILE}'"
                    )

                if check_proper_formatting is False:
                    continue

                # By now we now this function has a docstring and it has a CLI Example section
                # Let's now check if it's properly formatted
                if _check_cli_example_proper_formatting(docstring) is False:
                    errors += 1
                    exitcode = 1
                    ctx.error(
                        "The function {!r} on '{}' does not have a proper 'CLI Example:' section in "
                        "its docstring. The proper format is:\n"
                        "CLI Example:\n"
                        "\n"
                        ".. code-block:: bash\n"
                        "\n"
                        "    salt '*' <insert example here>\n".format(
                            funcdef.name,
                            path.relative_to(tools.utils.REPO_ROOT),
                        )
                    )
                    annotate(
                        ctx,
                        "warning",
                        path.relative_to(tools.utils.REPO_ROOT),
                        funcdef.lineno,
                        funcdef.body[0].lineno,
                        "Wrong format in 'CLI Example:' in docstring.\n"
                        "The proper format is:\n```"
                        "CLI Example:\n"
                        "\n"
                        ".. code-block:: bash\n"
                        "\n"
                        "    salt '*' <insert example here>\n```",
                    )
                    continue
        finally:
            if contents != path.read_text():
                path.write_text(contents)

    if warnings:
        ctx.warn(f"Found {warnings} warnings")
    if exitcode:
        ctx.error(f"Found {errors} errors")
    if os.environ.get("GH_ACTIONS_ANNOTATE") and (warnings or errors):
        github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if github_step_summary:
            with open(github_step_summary, "w", encoding="utf-8") as wfh:
                wfh.write(SUMMARY)
    ctx.exit(exitcode)


CHECK_VALID_VERSION_RE = re.compile(
    "(?P<vtype>(versionadded|versionchanged|deprecated))::(?P<version>.*)"
)


def _check_valid_versions_on_docstrings(docstring):
    for match in CHECK_VALID_VERSION_RE.finditer(docstring):
        vtype = match.group("vtype")
        version = match.group("version")
        versions = [vs.strip() for vs in version.split(",")]
        bad_versions = []
        for vs in versions:
            ret = subprocess.run(
                [sys.executable, str(SALT_CODE_DIR / "version.py"), vs], check=False
            )
            if ret.returncode:
                bad_versions.append(vs)
        if bad_versions:
            return vtype, ", ".join(bad_versions)
    return False


CLI_EXAMPLE_PRESENT_RE = re.compile(r"CLI Example(?:s)?:")


def _check_cli_example_present(docstring):
    return CLI_EXAMPLE_PRESENT_RE.search(docstring) is not None


CLI_EXAMPLE_PROPER_FORMATTING_RE = re.compile(
    r"CLI Example(?:s)?:\n\n.. code-block:: bash\n\n    salt (.*) '*'", re.MULTILINE
)


def _check_cli_example_proper_formatting(docstring):
    return CLI_EXAMPLE_PROPER_FORMATTING_RE.search(docstring) is not None

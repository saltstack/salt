"""
Connection module for Amazon ELB

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit elb credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        elb.keyid: GKTADJGHEIQSXMKKRBJ08H
        elb.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        elb.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto >= 2.33.0
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

import logging
import time

import salt.utils.json
import salt.utils.odict as odict
import salt.utils.versions

try:
    import boto
    import boto.ec2  # pylint: enable=unused-import
    from boto.ec2.elb import HealthCheck
    from boto.ec2.elb.attributes import (
        AccessLogAttribute,
        ConnectionDrainingAttribute,
        ConnectionSettingAttribute,
        CrossZoneLoadBalancingAttribute,
    )

    logging.getLogger("boto").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    # connection settings were added in 2.33.0
    has_boto_reqs = salt.utils.versions.check_boto_reqs(
        boto_ver="2.33.0", check_boto3=False
    )
    if has_boto_reqs is True:
        __utils__["boto.assign_funcs"](__name__, "elb", module="ec2.elb", pack=__salt__)
    return has_boto_reqs


def exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if an ELB exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.exists myelb region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        elb = conn.get_all_load_balancers(load_balancer_names=[name])
        if elb:
            return True
        else:
            log.debug("The load balancer does not exist in region %s", region)
            return False
    except boto.exception.BotoServerError as error:
        log.warning(error)
        return False


def get_all_elbs(region=None, key=None, keyid=None, profile=None):
    """
    Return all load balancers associated with an account

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.get_all_elbs region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        return [e for e in conn.get_all_load_balancers()]
    except boto.exception.BotoServerError as error:
        log.warning(error)
        return []


def list_elbs(region=None, key=None, keyid=None, profile=None):
    """
    Return names of all load balancers associated with an account

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.list_elbs region=us-east-1
    """

    return [
        e.name
        for e in get_all_elbs(region=region, key=key, keyid=keyid, profile=profile)
    ]


def get_elb_config(name, region=None, key=None, keyid=None, profile=None):
    """
    Get an ELB configuration.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.exists myelb region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30

    while retries:
        try:
            lb = conn.get_all_load_balancers(load_balancer_names=[name])
            lb = lb[0]
            ret = {}
            ret["availability_zones"] = lb.availability_zones
            listeners = []
            for _listener in lb.listeners:
                listener_dict = {}
                listener_dict["elb_port"] = _listener.load_balancer_port
                listener_dict["elb_protocol"] = _listener.protocol
                listener_dict["instance_port"] = _listener.instance_port
                listener_dict["instance_protocol"] = _listener.instance_protocol
                listener_dict["policies"] = _listener.policy_names
                if _listener.ssl_certificate_id:
                    listener_dict["certificate"] = _listener.ssl_certificate_id
                listeners.append(listener_dict)
            ret["listeners"] = listeners
            backends = []
            for _backend in lb.backends:
                bs_dict = {}
                bs_dict["instance_port"] = _backend.instance_port
                bs_dict["policies"] = [p.policy_name for p in _backend.policies]
                backends.append(bs_dict)
            ret["backends"] = backends
            ret["subnets"] = lb.subnets
            ret["security_groups"] = lb.security_groups
            ret["scheme"] = lb.scheme
            ret["dns_name"] = lb.dns_name
            ret["tags"] = _get_all_tags(conn, name)
            lb_policy_lists = [
                lb.policies.app_cookie_stickiness_policies,
                lb.policies.lb_cookie_stickiness_policies,
                lb.policies.other_policies,
            ]
            policies = []
            for policy_list in lb_policy_lists:
                policies += [p.policy_name for p in policy_list]
            ret["policies"] = policies
            ret["canonical_hosted_zone_name"] = lb.canonical_hosted_zone_name
            ret["canonical_hosted_zone_name_id"] = lb.canonical_hosted_zone_name_id
            ret["vpc_id"] = lb.vpc_id
            return ret
        except boto.exception.BotoServerError as error:
            if error.error_code == "Throttling":
                log.debug("Throttled by AWS API, will retry in 5 seconds.")
                time.sleep(5)
                retries -= 1
                continue
            log.error("Error fetching config for ELB %s: %s", name, error.message)
            log.error(error)
            return {}
    return {}


def listener_dict_to_tuple(listener):
    """
    Convert an ELB listener dict into a listener tuple used by certain parts of
    the AWS ELB API.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.listener_dict_to_tuple '{"elb_port":80,"instance_port":80,"elb_protocol":"HTTP"}'
    """
    # We define all listeners as complex listeners.
    if "instance_protocol" not in listener:
        instance_protocol = listener["elb_protocol"].upper()
    else:
        instance_protocol = listener["instance_protocol"].upper()
    listener_tuple = [
        listener["elb_port"],
        listener["instance_port"],
        listener["elb_protocol"],
        instance_protocol,
    ]
    if "certificate" in listener:
        listener_tuple.append(listener["certificate"])
    return tuple(listener_tuple)


def create(
    name,
    availability_zones,
    listeners,
    subnets=None,
    security_groups=None,
    scheme="internet-facing",
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create an ELB

    CLI example to create an ELB:

    .. code-block:: bash

        salt myminion boto_elb.create myelb '["us-east-1a", "us-east-1e"]' '{"elb_port": 443, "elb_protocol": "HTTPS", ...}' region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if exists(name, region, key, keyid, profile):
        return True
    if isinstance(availability_zones, str):
        availability_zones = salt.utils.json.loads(availability_zones)

    if isinstance(listeners, str):
        listeners = salt.utils.json.loads(listeners)

    _complex_listeners = []
    for listener in listeners:
        _complex_listeners.append(listener_dict_to_tuple(listener))

    try:
        lb = conn.create_load_balancer(
            name=name,
            zones=availability_zones,
            subnets=subnets,
            security_groups=security_groups,
            scheme=scheme,
            complex_listeners=_complex_listeners,
        )
        if lb:
            log.info("Created ELB %s", name)
            return True
        else:
            log.error("Failed to create ELB %s", name)
            return False
    except boto.exception.BotoServerError as error:
        log.error(
            "Failed to create ELB %s: %s: %s",
            name,
            error.error_code,
            error.message,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def delete(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete an ELB.

    CLI example to delete an ELB:

    .. code-block:: bash

        salt myminion boto_elb.delete myelb region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    try:
        conn.delete_load_balancer(name)
        log.info("Deleted ELB %s.", name)
        return True
    except boto.exception.BotoServerError as error:
        log.error("Failed to delete ELB %s", name, exc_info_on_loglevel=logging.DEBUG)
        return False


def create_listeners(name, listeners, region=None, key=None, keyid=None, profile=None):
    """
    Create listeners on an ELB.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.create_listeners myelb '[["HTTPS", "HTTP", 443, 80, "arn:aws:iam::11  11111:server-certificate/mycert"]]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(listeners, str):
        listeners = salt.utils.json.loads(listeners)

    _complex_listeners = []
    for listener in listeners:
        _complex_listeners.append(listener_dict_to_tuple(listener))
    try:
        conn.create_load_balancer_listeners(name, [], _complex_listeners)
        log.info("Created ELB listeners on %s", name)
        return True
    except boto.exception.BotoServerError as error:
        log.error(
            "Failed to create ELB listeners on %s: %s",
            name,
            error,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def delete_listeners(name, ports, region=None, key=None, keyid=None, profile=None):
    """
    Delete listeners on an ELB.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.delete_listeners myelb '[80,443]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(ports, str):
        ports = salt.utils.json.loads(ports)
    try:
        conn.delete_load_balancer_listeners(name, ports)
        log.info("Deleted ELB listeners on %s", name)
        return True
    except boto.exception.BotoServerError as error:
        log.error(
            "Failed to delete ELB listeners on %s: %s",
            name,
            error,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def apply_security_groups(
    name, security_groups, region=None, key=None, keyid=None, profile=None
):
    """
    Apply security groups to ELB.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.apply_security_groups myelb '["mysecgroup1"]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(security_groups, str):
        security_groups = salt.utils.json.loads(security_groups)
    try:
        conn.apply_security_groups_to_lb(name, security_groups)
        log.info("Applied security_groups on ELB %s", name)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.error("Failed to appply security_groups on ELB %s: %s", name, e.message)
        return False


def enable_availability_zones(
    name, availability_zones, region=None, key=None, keyid=None, profile=None
):
    """
    Enable availability zones for ELB.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.enable_availability_zones myelb '["us-east-1a"]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(availability_zones, str):
        availability_zones = salt.utils.json.loads(availability_zones)
    try:
        conn.enable_availability_zones(name, availability_zones)
        log.info("Enabled availability_zones on ELB %s", name)
        return True
    except boto.exception.BotoServerError as error:
        log.error("Failed to enable availability_zones on ELB %s: %s", name, error)
        return False


def disable_availability_zones(
    name, availability_zones, region=None, key=None, keyid=None, profile=None
):
    """
    Disable availability zones for ELB.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.disable_availability_zones myelb '["us-east-1a"]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(availability_zones, str):
        availability_zones = salt.utils.json.loads(availability_zones)
    try:
        conn.disable_availability_zones(name, availability_zones)
        log.info("Disabled availability_zones on ELB %s", name)
        return True
    except boto.exception.BotoServerError as error:
        log.error(
            "Failed to disable availability_zones on ELB %s: %s",
            name,
            error,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def attach_subnets(name, subnets, region=None, key=None, keyid=None, profile=None):
    """
    Attach ELB to subnets.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.attach_subnets myelb '["mysubnet"]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(subnets, str):
        subnets = salt.utils.json.loads(subnets)
    try:
        conn.attach_lb_to_subnets(name, subnets)
        log.info("Attached ELB %s on subnets.", name)
        return True
    except boto.exception.BotoServerError as error:
        log.error(
            "Failed to attach ELB %s on subnets: %s",
            name,
            error,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def detach_subnets(name, subnets, region=None, key=None, keyid=None, profile=None):
    """
    Detach ELB from subnets.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.detach_subnets myelb '["mysubnet"]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(subnets, str):
        subnets = salt.utils.json.loads(subnets)
    try:
        conn.detach_lb_from_subnets(name, subnets)
        log.info("Detached ELB %s from subnets.", name)
        return True
    except boto.exception.BotoServerError as error:
        log.error(
            "Failed to detach ELB %s from subnets: %s",
            name,
            error,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def get_attributes(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if attributes are set on an ELB.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.get_attributes myelb
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30

    while retries:
        try:
            lbattrs = conn.get_all_lb_attributes(name)
            ret = odict.OrderedDict()
            ret["access_log"] = odict.OrderedDict()
            ret["cross_zone_load_balancing"] = odict.OrderedDict()
            ret["connection_draining"] = odict.OrderedDict()
            ret["connecting_settings"] = odict.OrderedDict()
            al = lbattrs.access_log
            czlb = lbattrs.cross_zone_load_balancing
            cd = lbattrs.connection_draining
            cs = lbattrs.connecting_settings
            ret["access_log"]["enabled"] = al.enabled
            ret["access_log"]["s3_bucket_name"] = al.s3_bucket_name
            ret["access_log"]["s3_bucket_prefix"] = al.s3_bucket_prefix
            ret["access_log"]["emit_interval"] = al.emit_interval
            ret["cross_zone_load_balancing"]["enabled"] = czlb.enabled
            ret["connection_draining"]["enabled"] = cd.enabled
            ret["connection_draining"]["timeout"] = cd.timeout
            ret["connecting_settings"]["idle_timeout"] = cs.idle_timeout
            return ret
        except boto.exception.BotoServerError as e:
            if e.error_code == "Throttling":
                log.debug("Throttled by AWS API, will retry in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error("ELB %s does not exist: %s", name, e.message)
            return {}
    return {}


def set_attributes(name, attributes, region=None, key=None, keyid=None, profile=None):
    """
    Set attributes on an ELB.

    name (string)
        Name of the ELB instance to set attributes for

    attributes
        A dict of attributes to set.

        Valid attributes are:

        access_log (dict)
            enabled (bool)
                Enable storage of access logs.
            s3_bucket_name (string)
                The name of the S3 bucket to place logs.
            s3_bucket_prefix (string)
                Prefix for the log file name.
            emit_interval (int)
                Interval for storing logs in S3 in minutes. Valid values are
                5 and 60.

        connection_draining (dict)
            enabled (bool)
                Enable connection draining.
            timeout (int)
                Maximum allowed time in seconds for sending existing
                connections to an instance that is deregistering or unhealthy.
                Default is 300.

        cross_zone_load_balancing (dict)
            enabled (bool)
                Enable cross-zone load balancing.

    CLI example to set attributes on an ELB:

    .. code-block:: bash

        salt myminion boto_elb.set_attributes myelb '{"access_log": {"enabled": "true", "s3_bucket_name": "mybucket", "s3_bucket_prefix": "mylogs/", "emit_interval": "5"}}' region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    al = attributes.get("access_log", {})
    czlb = attributes.get("cross_zone_load_balancing", {})
    cd = attributes.get("connection_draining", {})
    cs = attributes.get("connecting_settings", {})
    if not al and not czlb and not cd and not cs:
        log.error("No supported attributes for ELB.")
        return False
    if al:
        _al = AccessLogAttribute()
        _al.enabled = al.get("enabled", False)
        if not _al.enabled:
            msg = "Access log attribute configured, but enabled config missing"
            log.error(msg)
            return False
        _al.s3_bucket_name = al.get("s3_bucket_name", None)
        _al.s3_bucket_prefix = al.get("s3_bucket_prefix", None)
        _al.emit_interval = al.get("emit_interval", None)
        added_attr = conn.modify_lb_attribute(name, "accessLog", _al)
        if added_attr:
            log.info("Added access_log attribute to %s elb.", name)
        else:
            log.error("Failed to add access_log attribute to %s elb.", name)
            return False
    if czlb:
        _czlb = CrossZoneLoadBalancingAttribute()
        _czlb.enabled = czlb["enabled"]
        added_attr = conn.modify_lb_attribute(
            name, "crossZoneLoadBalancing", _czlb.enabled
        )
        if added_attr:
            log.info("Added cross_zone_load_balancing attribute to %s elb.", name)
        else:
            log.error("Failed to add cross_zone_load_balancing attribute.")
            return False
    if cd:
        _cd = ConnectionDrainingAttribute()
        _cd.enabled = cd["enabled"]
        _cd.timeout = cd.get("timeout", 300)
        added_attr = conn.modify_lb_attribute(name, "connectionDraining", _cd)
        if added_attr:
            log.info("Added connection_draining attribute to %s elb.", name)
        else:
            log.error("Failed to add connection_draining attribute.")
            return False
    if cs:
        _cs = ConnectionSettingAttribute()
        _cs.idle_timeout = cs.get("idle_timeout", 60)
        added_attr = conn.modify_lb_attribute(name, "connectingSettings", _cs)
        if added_attr:
            log.info("Added connecting_settings attribute to %s elb.", name)
        else:
            log.error("Failed to add connecting_settings attribute.")
            return False
    return True


def get_health_check(name, region=None, key=None, keyid=None, profile=None):
    """
    Get the health check configured for this ELB.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.get_health_check myelb
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30

    while True:
        try:
            lb = conn.get_all_load_balancers(load_balancer_names=[name])
            lb = lb[0]
            ret = odict.OrderedDict()
            hc = lb.health_check
            ret["interval"] = hc.interval
            ret["target"] = hc.target
            ret["healthy_threshold"] = hc.healthy_threshold
            ret["timeout"] = hc.timeout
            ret["unhealthy_threshold"] = hc.unhealthy_threshold
            return ret
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, will retry in 5 seconds.")
                time.sleep(5)
                retries -= 1
                continue
            log.error("ELB %s not found.", name, exc_info_on_logleve=logging.DEBUG)
            return {}


def set_health_check(
    name, health_check, region=None, key=None, keyid=None, profile=None
):
    """
    Set attributes on an ELB.

    CLI example to set attributes on an ELB:

    .. code-block:: bash

        salt myminion boto_elb.set_health_check myelb '{"target": "HTTP:80/"}'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30

    hc = HealthCheck(**health_check)
    while True:
        try:
            conn.configure_health_check(name, hc)
            log.info("Configured health check on ELB %s", name)
            return True
        except boto.exception.BotoServerError as error:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, will retry in 5 seconds.")
                time.sleep(5)
                retries -= 1
                continue
            log.exception("Failed to configure health check on ELB %s", name)
            return False


def register_instances(
    name, instances, region=None, key=None, keyid=None, profile=None
):
    """
    Register instances with an ELB.  Instances is either a string
    instance id or a list of string instance id's.

    Returns:

    - ``True``: instance(s) registered successfully
    - ``False``: instance(s) failed to be registered

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.register_instances myelb instance_id
        salt myminion boto_elb.register_instances myelb "[instance_id,instance_id]"
    """
    # convert instances to list type, enabling consistent use of instances
    # variable throughout the register_instances method
    if isinstance(instances, str) or isinstance(instances, str):
        instances = [instances]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_instances = conn.register_instances(name, instances)
    except boto.exception.BotoServerError as error:
        log.warning(error)
        return False
    registered_instance_ids = [instance.id for instance in registered_instances]
    # register_failues is a set that will contain any instances that were not
    # able to be registered with the given ELB
    register_failures = set(instances).difference(set(registered_instance_ids))
    if register_failures:
        log.warning(
            "Instance(s): %s not registered with ELB %s.", list(register_failures), name
        )
        register_result = False
    else:
        register_result = True
    return register_result


def deregister_instances(
    name, instances, region=None, key=None, keyid=None, profile=None
):
    """
    Deregister instances with an ELB.  Instances is either a string
    instance id or a list of string instance id's.

    Returns:

    - ``True``: instance(s) deregistered successfully
    - ``False``: instance(s) failed to be deregistered
    - ``None``: instance(s) not valid or not registered, no action taken

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.deregister_instances myelb instance_id
        salt myminion boto_elb.deregister_instances myelb "[instance_id, instance_id]"
    """
    # convert instances to list type, enabling consistent use of instances
    # variable throughout the deregister_instances method
    if isinstance(instances, str) or isinstance(instances, str):
        instances = [instances]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_instances = conn.deregister_instances(name, instances)
    except boto.exception.BotoServerError as error:
        # if the instance(s) given as an argument are not members of the ELB
        # boto returns error.error_code == 'InvalidInstance'
        # deregister_instances returns "None" because the instances are
        # effectively deregistered from ELB
        if error.error_code == "InvalidInstance":
            log.warning(
                "One or more of instance(s) %s are not part of ELB %s. "
                "deregister_instances not performed.",
                instances,
                name,
            )
            return None
        else:
            log.warning(error)
            return False
    registered_instance_ids = [instance.id for instance in registered_instances]
    # deregister_failures is a set that will contain any instances that were
    # unable to be deregistered from the given ELB
    deregister_failures = set(instances).intersection(set(registered_instance_ids))
    if deregister_failures:
        log.warning(
            "Instance(s): %s not deregistered from ELB %s.",
            list(deregister_failures),
            name,
        )
        deregister_result = False
    else:
        deregister_result = True
    return deregister_result


def set_instances(
    name, instances, test=False, region=None, key=None, keyid=None, profile=None
):
    """
    Set the instances assigned to an ELB to exactly the list given

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.set_instances myelb region=us-east-1 instances="[instance_id,instance_id]"
    """
    ret = True
    current = {
        i["instance_id"] for i in get_instance_health(name, region, key, keyid, profile)
    }
    desired = set(instances)
    add = desired - current
    remove = current - desired
    if test:
        return bool(add or remove)
    if remove:
        if (
            deregister_instances(name, list(remove), region, key, keyid, profile)
            is False
        ):
            ret = False
    if add:
        if register_instances(name, list(add), region, key, keyid, profile) is False:
            ret = False
    return ret


def get_instance_health(
    name, region=None, key=None, keyid=None, profile=None, instances=None
):
    """
    Get a list of instances and their health state

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.get_instance_health myelb
        salt myminion boto_elb.get_instance_health myelb region=us-east-1 instances="[instance_id,instance_id]"
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        instance_states = conn.describe_instance_health(name, instances)
        ret = []
        for _instance in instance_states:
            ret.append(
                {
                    "instance_id": _instance.instance_id,
                    "description": _instance.description,
                    "state": _instance.state,
                    "reason_code": _instance.reason_code,
                }
            )
        return ret
    except boto.exception.BotoServerError as error:
        log.debug(error)
        return []


def create_policy(
    name,
    policy_name,
    policy_type,
    policy,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create an ELB policy.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.create_policy myelb mypolicy LBCookieStickinessPolicyType '{"CookieExpirationPeriod": 3600}'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return False
    try:
        success = conn.create_lb_policy(name, policy_name, policy_type, policy)
        if success:
            log.info("Created policy %s on ELB %s", policy_name, name)
            return True
        else:
            log.error("Failed to create policy %s on ELB %s", policy_name, name)
            return False
    except boto.exception.BotoServerError as e:
        log.error(
            "Failed to create policy %s on ELB %s: %s",
            policy_name,
            name,
            e.message,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def delete_policy(name, policy_name, region=None, key=None, keyid=None, profile=None):
    """
    Delete an ELB policy.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.delete_policy myelb mypolicy
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    try:
        conn.delete_lb_policy(name, policy_name)
        log.info("Deleted policy %s on ELB %s", policy_name, name)
        return True
    except boto.exception.BotoServerError as e:
        log.error(
            "Failed to delete policy %s on ELB %s: %s",
            policy_name,
            name,
            e.message,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False


def set_listener_policy(
    name, port, policies=None, region=None, key=None, keyid=None, profile=None
):
    """
    Set the policies of an ELB listener.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: Bash

        salt myminion boto_elb.set_listener_policy myelb 443 "[policy1,policy2]"
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    if policies is None:
        policies = []
    try:
        conn.set_lb_policies_of_listener(name, port, policies)
        log.info("Set policies %s on ELB %s listener %s", policies, name, port)
    except boto.exception.BotoServerError as e:
        log.info(
            "Failed to set policy %s on ELB %s listener %s: %s",
            policies,
            name,
            port,
            e.message,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False
    return True


def set_backend_policy(
    name, port, policies=None, region=None, key=None, keyid=None, profile=None
):
    """
    Set the policies of an ELB backend server.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.set_backend_policy myelb 443 "[policy1,policy2]"
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not exists(name, region, key, keyid, profile):
        return True
    if policies is None:
        policies = []
    try:
        conn.set_lb_policies_of_backend_server(name, port, policies)
        log.info("Set policies %s on ELB %s backend server %s", policies, name, port)
    except boto.exception.BotoServerError as e:
        log.info(
            "Failed to set policy %s on ELB %s backend server %s: %s",
            policies,
            name,
            port,
            e.message,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False
    return True


def set_tags(name, tags, region=None, key=None, keyid=None, profile=None):
    """
    Add the tags on an ELB

    .. versionadded:: 2016.3.0

    name
        name of the ELB

    tags
        dict of name/value pair tags

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.set_tags my-elb-name "{'Tag1': 'Value', 'Tag2': 'Another Value'}"
    """

    if exists(name, region, key, keyid, profile):
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        ret = _add_tags(conn, name, tags)
        return ret
    else:
        return False


def delete_tags(name, tags, region=None, key=None, keyid=None, profile=None):
    """
    Add the tags on an ELB

    name
        name of the ELB

    tags
        list of tags to remove

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elb.delete_tags my-elb-name ['TagToRemove1', 'TagToRemove2']
    """
    if exists(name, region, key, keyid, profile):
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        ret = _remove_tags(conn, name, tags)
        return ret
    else:
        return False


def _build_tag_param_list(params, tags):
    """
    helper function to build a tag parameter list to send
    """
    keys = sorted(tags.keys())
    i = 1
    for key in keys:
        value = tags[key]
        params["Tags.member.{}.Key".format(i)] = key
        if value is not None:
            params["Tags.member.{}.Value".format(i)] = value
        i += 1


def _get_all_tags(conn, load_balancer_names=None):
    """
    Retrieve all the metadata tags associated with your ELB(s).

    :type load_balancer_names: list
    :param load_balancer_names: An optional list of load balancer names.

    :rtype: list
    :return: A list of :class:`boto.ec2.elb.tag.Tag` objects
    """
    params = {}
    if load_balancer_names:
        conn.build_list_params(
            params, load_balancer_names, "LoadBalancerNames.member.%d"
        )

    tags = conn.get_object(
        "DescribeTags",
        params,
        __utils__["boto_elb_tag.get_tag_descriptions"](),
        verb="POST",
    )
    if tags[load_balancer_names]:
        return tags[load_balancer_names]
    else:
        return None


def _add_tags(conn, load_balancer_names, tags):
    """
    Create new metadata tags for the specified resource ids.

    :type load_balancer_names: list
    :param load_balancer_names: A list of load balancer names.

    :type tags: dict
    :param tags: A dictionary containing the name/value pairs.
                 If you want to create only a tag name, the
                 value for that tag should be the empty string
                 (e.g. '').
    """
    params = {}
    conn.build_list_params(params, load_balancer_names, "LoadBalancerNames.member.%d")
    _build_tag_param_list(params, tags)
    return conn.get_status("AddTags", params, verb="POST")


def _remove_tags(conn, load_balancer_names, tags):
    """
    Delete metadata tags for the specified resource ids.

    :type load_balancer_names: list
    :param load_balancer_names: A list of load balancer names.

    :type tags: list
    :param tags: A list containing just tag names for the tags to be
                 deleted.
    """
    params = {}
    conn.build_list_params(params, load_balancer_names, "LoadBalancerNames.member.%d")
    conn.build_list_params(params, tags, "Tags.member.%d.Key")
    return conn.get_status("RemoveTags", params, verb="POST")

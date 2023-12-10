"""
Connection module for Amazon Security Groups

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit ec2 credentials but can
    also utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        secgroup.keyid: GKTADJGHEIQSXMKKRBJ08H
        secgroup.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        secgroup.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import logging

import salt.utils.odict as odict
import salt.utils.versions
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)


try:
    # pylint: disable=unused-import
    import boto
    import boto.ec2

    # pylint: enable=unused-import
    logging.getLogger("boto").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    """
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    """
    # Boto < 2.4.0 GroupOrCIDR objects have different attributes than
    # Boto >= 2.4.0 GroupOrCIDR objects
    # Differences include no group_id attribute in Boto < 2.4.0 and returning
    # a groupId attribute when a GroupOrCIDR object authorizes an IP range
    # Support for Boto < 2.4.0 can be added if needed
    has_boto_reqs = salt.utils.versions.check_boto_reqs(
        boto_ver="2.4.0", check_boto3=False
    )
    if has_boto_reqs is True:
        __utils__["boto.assign_funcs"](__name__, "ec2", pack=__salt__)
    return has_boto_reqs


def exists(
    name=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    vpc_id=None,
    vpc_name=None,
    group_id=None,
):
    """
    Check to see if a security group exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.exists mysecgroup
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(
        conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        group_id=group_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if group:
        return True
    else:
        return False


def _vpc_name_to_id(
    vpc_id=None, vpc_name=None, region=None, key=None, keyid=None, profile=None
):
    data = __salt__["boto_vpc.get_id"](
        name=vpc_name, region=region, key=key, keyid=keyid, profile=profile
    )
    return data.get("id")


def _split_rules(rules):
    """
    Split rules with combined grants into individual rules.

    Amazon returns a set of rules with the same protocol, from and to ports
    together as a single rule with a set of grants. Authorizing and revoking
    rules, however, is done as a split set of rules. This function splits the
    rules up.
    """
    split = []
    for rule in rules:
        ip_protocol = rule.get("ip_protocol")
        to_port = rule.get("to_port")
        from_port = rule.get("from_port")
        grants = rule.get("grants")
        for grant in grants:
            _rule = {
                "ip_protocol": ip_protocol,
                "to_port": to_port,
                "from_port": from_port,
            }
            for key, val in grant.items():
                _rule[key] = val
            split.append(_rule)
    return split


def _get_group(
    conn=None,
    name=None,
    vpc_id=None,
    vpc_name=None,
    group_id=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):  # pylint: disable=W0613
    """
    Get a group object given a name, name and vpc_id/vpc_name or group_id. Return
    a boto.ec2.securitygroup.SecurityGroup object if the group is found, else
    return None.
    """
    if vpc_name and vpc_id:
        raise SaltInvocationError(
            "The params 'vpc_id' and 'vpc_name' are mutually exclusive."
        )
    if vpc_name:
        try:
            vpc_id = _vpc_name_to_id(
                vpc_id=vpc_id,
                vpc_name=vpc_name,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
        except boto.exception.BotoServerError as e:
            log.debug(e)
            return None
    if name:
        if vpc_id is None:
            log.debug("getting group for %s", name)
            group_filter = {"group-name": name}
            filtered_groups = conn.get_all_security_groups(filters=group_filter)
            # security groups can have the same name if groups exist in both
            # EC2-Classic and EC2-VPC
            # iterate through groups to ensure we return the EC2-Classic
            # security group
            for group in filtered_groups:
                # a group in EC2-Classic will have vpc_id set to None
                if group.vpc_id is None:
                    return group
            # If there are more security groups, and no vpc_id, we can't know which one to choose.
            if len(filtered_groups) > 1:
                raise CommandExecutionError(
                    "Security group belongs to more VPCs, specify the VPC ID!"
                )
            elif len(filtered_groups) == 1:
                return filtered_groups[0]
            return None
        elif vpc_id:
            log.debug("getting group for %s in vpc_id %s", name, vpc_id)
            group_filter = {"group-name": name, "vpc_id": vpc_id}
            filtered_groups = conn.get_all_security_groups(filters=group_filter)
            if len(filtered_groups) == 1:
                return filtered_groups[0]
            else:
                return None
        else:
            return None
    elif group_id:
        try:
            groups = conn.get_all_security_groups(group_ids=[group_id])
        except boto.exception.BotoServerError as e:
            log.debug(e)
            return None
        if len(groups) == 1:
            return groups[0]
        else:
            return None
    else:
        return None


def _parse_rules(sg, rules):
    _rules = []
    for rule in rules:
        log.debug("examining rule %s for group %s", rule, sg.id)
        attrs = ["ip_protocol", "from_port", "to_port", "grants"]
        _rule = odict.OrderedDict()
        for attr in attrs:
            val = getattr(rule, attr)
            if not val:
                continue
            if attr == "grants":
                _grants = []
                for grant in val:
                    log.debug("examining grant %s for", grant)
                    g_attrs = {
                        "name": "source_group_name",
                        "owner_id": "source_group_owner_id",
                        "group_id": "source_group_group_id",
                        "cidr_ip": "cidr_ip",
                    }
                    _grant = odict.OrderedDict()
                    for g_attr, g_attr_map in g_attrs.items():
                        g_val = getattr(grant, g_attr)
                        if not g_val:
                            continue
                        _grant[g_attr_map] = g_val
                    _grants.append(_grant)
                _rule["grants"] = _grants
            elif attr == "from_port":
                _rule[attr] = int(val)
            elif attr == "to_port":
                _rule[attr] = int(val)
            else:
                _rule[attr] = val
        _rules.append(_rule)
    return _rules


def get_all_security_groups(
    groupnames=None,
    group_ids=None,
    filters=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Return a list of all Security Groups matching the given criteria and
    filters.

    Note that the ``groupnames`` argument only functions correctly for EC2
    Classic and default VPC Security Groups.  To find groups by name in other
    VPCs you'll want to use the ``group-name`` filter instead.

    The valid keys for the ``filters`` argument can be found in `AWS's API
    documentation
    <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSecurityGroups.html>`_.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.get_all_security_groups filters='{group-name: mygroup}'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(groupnames, str):
        groupnames = [groupnames]
    if isinstance(group_ids, str):
        groupnames = [group_ids]

    interesting = [
        "description",
        "id",
        "instances",
        "name",
        "owner_id",
        "region",
        "rules",
        "rules_egress",
        "tags",
        "vpc_id",
    ]
    ret = []
    try:
        r = conn.get_all_security_groups(
            groupnames=groupnames, group_ids=group_ids, filters=filters
        )
        for g in r:
            n = {}
            for a in interesting:
                v = getattr(g, a, None)
                if a == "region":
                    v = v.name
                elif a in ("rules", "rules_egress"):
                    v = _parse_rules(g, v)
                elif a == "instances":
                    v = [i.id for i in v()]
                n[a] = v
            ret += [n]
        return ret
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return []


def get_group_id(
    name, vpc_id=None, vpc_name=None, region=None, key=None, keyid=None, profile=None
):
    """
    Get a Group ID given a Group Name or Group Name and VPC ID

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.get_group_id mysecgroup
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if name.startswith("sg-"):
        log.debug("group %s is a group id. get_group_id not called.", name)
        return name
    group = _get_group(
        conn=conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    return getattr(group, "id", None)


def convert_to_group_ids(
    groups, vpc_id=None, vpc_name=None, region=None, key=None, keyid=None, profile=None
):
    """
    Given a list of security groups and a vpc_id, convert_to_group_ids will
    convert all list items in the given list to security group ids.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.convert_to_group_ids mysecgroup vpc-89yhh7h
    """
    log.debug("security group contents %s pre-conversion", groups)
    group_ids = []
    for group in groups:
        group_id = get_group_id(
            name=group,
            vpc_id=vpc_id,
            vpc_name=vpc_name,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not group_id:
            # Security groups are a big deal - need to fail if any can't be resolved...
            # But... if we're running in test mode, it may just be that the SG is scheduled
            # to be created, and thus WOULD have been there if running "for real"...
            if __opts__["test"]:
                log.warning(
                    "Security Group `%s` could not be resolved to an ID.  This may "
                    "cause a failure when not running in test mode.",
                    group,
                )
                return []
            else:
                raise CommandExecutionError(
                    "Could not resolve Security Group name {} to a Group ID".format(
                        group
                    )
                )
        else:
            group_ids.append(str(group_id))
    log.debug("security group contents %s post-conversion", group_ids)
    return group_ids


def get_config(
    name=None,
    group_id=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    vpc_id=None,
    vpc_name=None,
):
    """
    Get the configuration for a security group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.get_config mysecgroup
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    sg = _get_group(
        conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        group_id=group_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if sg:
        ret = odict.OrderedDict()
        ret["name"] = sg.name
        # TODO: add support for vpc_id in return
        # ret['vpc_id'] = sg.vpc_id
        ret["group_id"] = sg.id
        ret["owner_id"] = sg.owner_id
        ret["description"] = sg.description
        ret["tags"] = sg.tags
        _rules = _parse_rules(sg, sg.rules)
        _rules_egress = _parse_rules(sg, sg.rules_egress)
        ret["rules"] = _split_rules(_rules)
        ret["rules_egress"] = _split_rules(_rules_egress)
        return ret
    else:
        return None


def create(
    name,
    description,
    vpc_id=None,
    vpc_name=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create a security group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.create mysecgroup 'My Security Group'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not vpc_id and vpc_name:
        try:
            vpc_id = _vpc_name_to_id(
                vpc_id=vpc_id,
                vpc_name=vpc_name,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
        except boto.exception.BotoServerError as e:
            log.debug(e)
            return False

    created = conn.create_security_group(name, description, vpc_id)
    if created:
        log.info("Created security group %s.", name)
        return True
    else:
        msg = "Failed to create security group {}.".format(name)
        log.error(msg)
        return False


def delete(
    name=None,
    group_id=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    vpc_id=None,
    vpc_name=None,
):
    """
    Delete a security group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.delete mysecgroup
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(
        conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        group_id=group_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if group:
        deleted = conn.delete_security_group(group_id=group.id)
        if deleted:
            log.info("Deleted security group %s with id %s.", group.name, group.id)
            return True
        else:
            msg = "Failed to delete security group {}.".format(name)
            log.error(msg)
            return False
    else:
        log.debug("Security group not found.")
        return False


def authorize(
    name=None,
    source_group_name=None,
    source_group_owner_id=None,
    ip_protocol=None,
    from_port=None,
    to_port=None,
    cidr_ip=None,
    group_id=None,
    source_group_group_id=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    vpc_id=None,
    vpc_name=None,
    egress=False,
):
    """
    Add a new rule to an existing security group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.authorize mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='['10.0.0.0/8', '192.168.0.0/24']'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(
        conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        group_id=group_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if group:
        try:
            added = None
            if not egress:
                added = conn.authorize_security_group(
                    src_security_group_name=source_group_name,
                    src_security_group_owner_id=source_group_owner_id,
                    ip_protocol=ip_protocol,
                    from_port=from_port,
                    to_port=to_port,
                    cidr_ip=cidr_ip,
                    group_id=group.id,
                    src_security_group_group_id=source_group_group_id,
                )
            else:
                added = conn.authorize_security_group_egress(
                    ip_protocol=ip_protocol,
                    from_port=from_port,
                    to_port=to_port,
                    cidr_ip=cidr_ip,
                    group_id=group.id,
                    src_group_id=source_group_group_id,
                )
            if added:
                log.info(
                    "Added rule to security group %s with id %s", group.name, group.id
                )
                return True
            else:
                msg = "Failed to add rule to security group {} with id {}.".format(
                    group.name, group.id
                )
                log.error(msg)
                return False
        except boto.exception.EC2ResponseError as e:
            # if we are trying to add the same rule then we are already in the desired state, return true
            if e.error_code == "InvalidPermission.Duplicate":
                return True
            msg = "Failed to add rule to security group {} with id {}.".format(
                group.name, group.id
            )
            log.error(msg)
            log.error(e)
            return False
    else:
        log.error("Failed to add rule to security group.")
        return False


def revoke(
    name=None,
    source_group_name=None,
    source_group_owner_id=None,
    ip_protocol=None,
    from_port=None,
    to_port=None,
    cidr_ip=None,
    group_id=None,
    source_group_group_id=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    vpc_id=None,
    vpc_name=None,
    egress=False,
):
    """
    Remove a rule from an existing security group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.revoke mysecgroup ip_protocol=tcp from_port=80 to_port=80 cidr_ip='10.0.0.0/8'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    group = _get_group(
        conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        group_id=group_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if group:
        try:
            revoked = None
            if not egress:
                revoked = conn.revoke_security_group(
                    src_security_group_name=source_group_name,
                    src_security_group_owner_id=source_group_owner_id,
                    ip_protocol=ip_protocol,
                    from_port=from_port,
                    to_port=to_port,
                    cidr_ip=cidr_ip,
                    group_id=group.id,
                    src_security_group_group_id=source_group_group_id,
                )
            else:
                revoked = conn.revoke_security_group_egress(
                    ip_protocol=ip_protocol,
                    from_port=from_port,
                    to_port=to_port,
                    cidr_ip=cidr_ip,
                    group_id=group.id,
                    src_group_id=source_group_group_id,
                )

            if revoked:
                log.info(
                    "Removed rule from security group %s with id %s.",
                    group.name,
                    group.id,
                )
                return True
            else:
                msg = "Failed to remove rule from security group {} with id {}.".format(
                    group.name, group.id
                )
                log.error(msg)
                return False
        except boto.exception.EC2ResponseError as e:
            msg = "Failed to remove rule from security group {} with id {}.".format(
                group.name, group.id
            )
            log.error(msg)
            log.error(e)
            return False
    else:
        log.error("Failed to remove rule from security group.")
        return False


def _find_vpcs(
    vpc_id=None,
    vpc_name=None,
    cidr=None,
    tags=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given VPC properties, find and return matching VPC ids.
    Borrowed from boto_vpc; these could be refactored into a common library
    """
    if all((vpc_id, vpc_name)):
        raise SaltInvocationError("Only one of vpc_name or vpc_id may be provided.")

    if not any((vpc_id, vpc_name, tags, cidr)):
        raise SaltInvocationError(
            "At least one of the following must be "
            "provided: vpc_id, vpc_name, cidr or tags."
        )

    local_get_conn = __utils__["boto.get_connection_func"]("vpc")
    conn = local_get_conn(region=region, key=key, keyid=keyid, profile=profile)
    filter_parameters = {"filters": {}}

    if vpc_id:
        filter_parameters["vpc_ids"] = [vpc_id]

    if cidr:
        filter_parameters["filters"]["cidr"] = cidr

    if vpc_name:
        filter_parameters["filters"]["tag:Name"] = vpc_name

    if tags:
        for tag_name, tag_value in tags.items():
            filter_parameters["filters"]["tag:{}".format(tag_name)] = tag_value

    vpcs = conn.get_all_vpcs(**filter_parameters)
    log.debug(
        "The filters criteria %s matched the following VPCs:%s", filter_parameters, vpcs
    )

    if vpcs:
        return [vpc.id for vpc in vpcs]
    else:
        return []


def set_tags(
    tags,
    name=None,
    group_id=None,
    vpc_name=None,
    vpc_id=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Sets tags on a security group.

    .. versionadded:: 2016.3.0

    tags
        a dict of key:value pair of tags to set on the security group

    name
        the name of the security group

    group_id
        the group id of the security group (in lie of a name/vpc combo)

    vpc_name
        the name of the vpc to search the named group for

    vpc_id
        the id of the vpc, in lieu of the vpc_name

    region
        the amazon region

    key
        amazon key

    keyid
        amazon keyid

    profile
        amazon profile

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.set_tags "{'TAG1': 'Value1', 'TAG2': 'Value2'}" security_group_name vpc_id=vpc-13435 profile=my_aws_profile
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    secgrp = _get_group(
        conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        group_id=group_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )

    if secgrp:
        if isinstance(tags, dict):
            secgrp.add_tags(tags)
        else:
            msg = "Tags must be a dict of tagname:tagvalue"
            raise SaltInvocationError(msg)
    else:
        msg = "The security group could not be found"
        raise SaltInvocationError(msg)
    return True


def delete_tags(
    tags,
    name=None,
    group_id=None,
    vpc_name=None,
    vpc_id=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Deletes tags from a security group.

    .. versionadded:: 2016.3.0

    tags
        a list of tags to remove

    name
        the name of the security group

    group_id
        the group id of the security group (in lie of a name/vpc combo)

    vpc_name
        the name of the vpc to search the named group for

    vpc_id
        the id of the vpc, in lieu of the vpc_name

    region
        the amazon region

    key
        amazon key

    keyid
        amazon keyid

    profile
        amazon profile

    CLI Example:

    .. code-block:: bash

        salt myminion boto_secgroup.delete_tags ['TAG_TO_DELETE1','TAG_TO_DELETE2'] security_group_name vpc_id=vpc-13435 profile=my_aws_profile
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    secgrp = _get_group(
        conn,
        name=name,
        vpc_id=vpc_id,
        vpc_name=vpc_name,
        group_id=group_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if secgrp:
        if isinstance(tags, list):
            tags_to_remove = {}
            for tag in tags:
                tags_to_remove[tag] = None
            secgrp.remove_tags(tags_to_remove)
        else:
            msg = "Tags must be a list of tagnames to remove from the security group"
            raise SaltInvocationError(msg)
    else:
        msg = "The security group could not be found"
        raise SaltInvocationError(msg)
    return True

"""
Manage Route53 records with Boto 3

.. versionadded:: 2017.7.0

Create and delete Route53 records. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit route53 credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    route53.keyid: GKTADJGHEIQSXMKKRBJ08H
    route53.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
      keyid: GKTADJGHEIQSXMKKRBJ08H
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
      region: us-east-1

.. code-block:: yaml

    An exciting new AWS Route 53 Hosted Zone:
      boto_route53.hosted_zone_present:
        - Name: example.com.
        - PrivateZone: true
        - VPCs:
          - VPCName: MyLittleVPC
            VPCRegion: us-east-1
          - VPCId: vpc-12345678
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    mycnamerecord:
      boto_route53.rr_present:
        - Name: test.example.com.
        - ResourceRecords:
          - my-elb.us-east-1.elb.amazonaws.com.
        - DomainName: example.com.
        - TTL: 60
        - Type: CNAME
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

"""

# keep lint from choking
# pylint: disable=W0106


import logging
import uuid

import salt.utils.data
import salt.utils.dictupdate
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto is available.
    """
    if "boto3_route53.find_hosted_zone" in __salt__:
        return "boto3_route53"
    return (False, "boto3_route53 module could not be loaded")


def hosted_zone_present(
    name,
    Name=None,
    PrivateZone=False,
    CallerReference=None,
    Comment=None,
    VPCs=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure a hosted zone exists with the given attributes.

    name
        The name of the state definition.

    Name
        The name of the domain. This should be a fully-specified domain, and should terminate with a
        period. This is the name you have registered with your DNS registrar. It is also the name
        you will delegate from your registrar to the Amazon Route 53 delegation servers returned in
        response to this request.  If not provided, the value of name will be used.

    PrivateZone
        Set True if creating a private hosted zone.  If true, then 'VPCs' is also required.

    Comment
        Any comments you want to include about the hosted zone.

    CallerReference
        A unique string that identifies the request and that allows create_hosted_zone() calls to be
        retried without the risk of executing the operation twice.  This helps ensure idempotency
        across state calls, but can cause issues if a zone is deleted and then an attempt is made
        to recreate it with the same CallerReference.  If not provided, a unique UUID will be
        generated at each state run, which can potentially lead to duplicate zones being created if
        the state is run again while the previous zone creation is still in PENDING status (which
        can occasionally take several minutes to clear).  Maximum length of 128.

    VPCs
        A list of dicts, each dict composed of a VPCRegion, and either a VPCId or a VPCName.
        Note that this param is ONLY used if PrivateZone == True

        VPCId
            When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
            required.  Exclusive with VPCName.

        VPCName
            When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
            required.  Exclusive with VPCId.

        VPCRegion
            When creating a private hosted zone, the region of the associated VPC is required.  If
            not provided, an effort will be made to determine it from VPCId or VPCName, if
            possible.  This will fail if a given VPCName exists in multiple regions visible to the
            bound account, in which case you'll need to provide an explicit value for VPCRegion.
    """
    Name = Name if Name else name

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if not PrivateZone and VPCs:
        raise SaltInvocationError(
            "Parameter 'VPCs' is invalid when creating a public zone."
        )
    if PrivateZone and not VPCs:
        raise SaltInvocationError(
            "Parameter 'VPCs' is required when creating a private zone."
        )
    if VPCs:
        if not isinstance(VPCs, list):
            raise SaltInvocationError("Parameter 'VPCs' must be a list of dicts.")
        for v in VPCs:
            if not isinstance(v, dict) or not salt.utils.data.exactly_one(
                (v.get("VPCId"), v.get("VPCName"))
            ):
                raise SaltInvocationError(
                    "Parameter 'VPCs' must be a list of dicts, each composed "
                    "of either a 'VPCId' or a 'VPCName', and optionally a "
                    "'VPCRegion', to help distinguish between multitple matches."
                )
    # Massage VPCs into something AWS will accept...
    fixed_vpcs = []
    if PrivateZone:
        for v in VPCs:
            VPCId = v.get("VPCId")
            VPCName = v.get("VPCName")
            VPCRegion = v.get("VPCRegion")
            VPCs = __salt__["boto_vpc.describe_vpcs"](
                vpc_id=VPCId,
                name=VPCName,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            ).get("vpcs", [])
            if VPCRegion and VPCs:
                VPCs = [v for v in VPCs if v["region"] == VPCRegion]
            if not VPCs:
                ret["comment"] = (
                    "A VPC matching given criteria (vpc: {} / vpc_region: {}) not "
                    "found.".format(VPCName or VPCId, VPCRegion)
                )
                log.error(ret["comment"])
                ret["result"] = False
                return ret
            if len(VPCs) > 1:
                ret["comment"] = (
                    "Multiple VPCs matching given criteria (vpc: {} / vpc_region: "
                    "{}) found: {}.".format(
                        VPCName or VPCId, VPCRegion, ", ".join([v["id"] for v in VPCs])
                    )
                )
                log.error(ret["comment"])
                ret["result"] = False
                return ret
            vpc = VPCs[0]
            if VPCName:
                VPCId = vpc["id"]
            if not VPCRegion:
                VPCRegion = vpc["region"]
            fixed_vpcs += [{"VPCId": VPCId, "VPCRegion": VPCRegion}]

    create = False
    update_comment = False
    add_vpcs = []
    del_vpcs = []
    args = {
        "Name": Name,
        "PrivateZone": PrivateZone,
        "region": region,
        "key": key,
        "keyid": keyid,
        "profile": profile,
    }
    zone = __salt__["boto3_route53.find_hosted_zone"](**args)
    if not zone:
        create = True
        # Grrrr - can only pass one VPC when initially creating a private zone...
        # The rest have to be added (one-by-one) later in a separate step.
        if len(fixed_vpcs) > 1:
            add_vpcs = fixed_vpcs[1:]
            fixed_vpcs = fixed_vpcs[:1]
        CallerReference = CallerReference if CallerReference else str(uuid.uuid4())
    else:
        # Currently the only modifiable traits about a zone are associated VPCs and the comment.
        zone = zone[0]
        if PrivateZone:
            for z in zone.get("VPCs"):
                if z not in fixed_vpcs:
                    del_vpcs += [z]
            for z in fixed_vpcs:
                if z not in zone.get("VPCs"):
                    add_vpcs += [z]
        if zone["HostedZone"]["Config"].get("Comment") != Comment:
            update_comment = True

    if not (create or add_vpcs or del_vpcs or update_comment):
        ret["comment"] = f"Hostd Zone {Name} already in desired state"
        return ret

    if create:
        if __opts__["test"]:
            ret["comment"] = "Route 53 {} hosted zone {} would be created.".format(
                "private" if PrivateZone else "public", Name
            )
            ret["result"] = None
            return ret
        vpc_id = fixed_vpcs[0].get("VPCId") if fixed_vpcs else None
        vpc_region = fixed_vpcs[0].get("VPCRegion") if fixed_vpcs else None
        newzone = __salt__["boto3_route53.create_hosted_zone"](
            Name=Name,
            CallerReference=CallerReference,
            Comment=Comment,
            PrivateZone=PrivateZone,
            VPCId=vpc_id,
            VPCRegion=vpc_region,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if newzone:
            newzone = newzone[0]
            ret["comment"] = "Route 53 {} hosted zone {} successfully created".format(
                "private" if PrivateZone else "public", Name
            )
            log.info(ret["comment"])
            ret["changes"]["new"] = newzone
        else:
            ret["comment"] = "Creation of Route 53 {} hosted zone {} failed".format(
                "private" if PrivateZone else "public", Name
            )
            log.error(ret["comment"])
            ret["result"] = False
            return ret

    if update_comment:
        if __opts__["test"]:
            ret["comment"] = (
                "Route 53 {} hosted zone {} comment would be updated.".format(
                    "private" if PrivateZone else "public", Name
                )
            )
            ret["result"] = None
            return ret
        r = __salt__["boto3_route53.update_hosted_zone_comment"](
            Name=Name,
            Comment=Comment,
            PrivateZone=PrivateZone,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if r:
            r = r[0]
            msg = "Route 53 {} hosted zone {} comment successfully updated".format(
                "private" if PrivateZone else "public", Name
            )
            log.info(msg)
            ret["comment"] = "  ".join([ret["comment"], msg])
            ret["changes"]["old"] = zone
            ret["changes"]["new"] = salt.utils.dictupdate.update(
                ret["changes"].get("new", {}), r
            )
        else:
            ret["comment"] = (
                "Update of Route 53 {} hosted zone {} comment failed".format(
                    "private" if PrivateZone else "public", Name
                )
            )
            log.error(ret["comment"])
            ret["result"] = False
            return ret

    if add_vpcs or del_vpcs:
        if __opts__["test"]:
            ret["comment"] = (
                "Route 53 {} hosted zone {} associated VPCs would be updated.".format(
                    "private" if PrivateZone else "public", Name
                )
            )
            ret["result"] = None
            return ret
        all_added = True
        all_deled = True
        for (
            vpc
        ) in add_vpcs:  # Add any new first to avoid the "can't delete last VPC" errors.
            r = __salt__["boto3_route53.associate_vpc_with_hosted_zone"](
                Name=Name,
                VPCId=vpc["VPCId"],
                VPCRegion=vpc["VPCRegion"],
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if not r:
                all_added = False
        for vpc in del_vpcs:
            r = __salt__["boto3_route53.disassociate_vpc_from_hosted_zone"](
                Name=Name,
                VPCId=vpc["VPCId"],
                VPCRegion=vpc["VPCRegion"],
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if not r:
                all_deled = False

        ret["changes"]["old"] = zone
        ret["changes"]["new"] = __salt__["boto3_route53.find_hosted_zone"](**args)
        if all_added and all_deled:
            msg = "Route 53 {} hosted zone {} associated VPCs successfully updated".format(
                "private" if PrivateZone else "public", Name
            )
            log.info(msg)
            ret["comment"] = "  ".join([ret["comment"], msg])
        else:
            ret["comment"] = (
                "Update of Route 53 {} hosted zone {} associated VPCs failed".format(
                    "private" if PrivateZone else "public", Name
                )
            )
            log.error(ret["comment"])
            ret["result"] = False
            return ret

    return ret


def hosted_zone_absent(
    name, Name=None, PrivateZone=False, region=None, key=None, keyid=None, profile=None
):
    """
    Ensure the Route53 Hostes Zone described is absent

    name
        The name of the state definition.

    Name
        The name of the domain. This should be a fully-specified domain, and should terminate with a
        period.  If not provided, the value of name will be used.

    PrivateZone
        Set True if deleting a private hosted zone.

    """
    Name = Name if Name else name

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    args = {
        "Name": Name,
        "PrivateZone": PrivateZone,
        "region": region,
        "key": key,
        "keyid": keyid,
        "profile": profile,
    }
    zone = __salt__["boto3_route53.find_hosted_zone"](**args)
    if not zone:
        ret["comment"] = "Route 53 {} hosted zone {} already absent".format(
            "private" if PrivateZone else "public", Name
        )
        log.info(ret["comment"])
        return ret
    if __opts__["test"]:
        ret["comment"] = "Route 53 {} hosted zone {} would be deleted".format(
            "private" if PrivateZone else "public", Name
        )
        ret["result"] = None
        return ret
    zone = zone[0]
    Id = zone["HostedZone"]["Id"]
    if __salt__["boto3_route53.delete_hosted_zone"](
        Id=Id, region=region, key=key, keyid=keyid, profile=profile
    ):
        ret["comment"] = "Route 53 {} hosted zone {} deleted".format(
            "private" if PrivateZone else "public", Name
        )
        log.info(ret["comment"])
        ret["changes"]["old"] = zone
        ret["changes"]["new"] = None
    else:
        ret["comment"] = "Failed to delete Route 53 {} hosted zone {}".format(
            "private" if PrivateZone else "public", Name
        )
        log.info(ret["comment"])
        ret["result"] = False
        return ret

    return ret


def rr_present(
    name,
    HostedZoneId=None,
    DomainName=None,
    PrivateZone=False,
    Name=None,
    Type=None,
    SetIdentifier=None,
    Weight=None,
    Region=None,
    GeoLocation=None,
    Failover=None,
    TTL=None,
    ResourceRecords=None,
    AliasTarget=None,
    HealthCheckId=None,
    TrafficPolicyInstanceId=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure the Route53 record is present.

    name
        The name of the state definition.  This will be used for Name if the latter is
        not provided.

    HostedZoneId
        The ID of a zone to create the record in.  Exclusive with DomainName.

    DomainName
        The domain name of a zone to create the record in.  Exclusive with HostedZoneId.

    PrivateZone
        Set to True if the resource record should be in a private zone, False if public.

    Name
        Name of the Route 53 resource record being managed.

    Type
        The record type (A, NS, MX, TXT, etc.)

    SetIdentifier
        Valid for Weighted, Latency, Geolocation, and Failover resource record sets only.
        An identifier that differentiates among multiple resource record sets that have the same
        combination of DNS name and type.  The value of SetIdentifier must be unique for each
        resource record set that has the same combination of DNS name and type. Omit SetIdentifier
        for any other types of record sets.

    Weight
        Valid for Weighted resource record sets only.  Among resource record sets that have the
        same combination of DNS name and type, a value that determines the proportion of DNS
        queries that Amazon Route 53 responds to using the current resource record set. Amazon Route
        53 calculates the sum of the weights for the resource record sets that have the same
        combination of DNS name and type. Amazon Route 53 then responds to queries based on the
        ratio of a resource's weight to the total.

        Note the following:

        - You must specify a value for the Weight element for every weighted resource record set.
        - You can only specify one ResourceRecord per weighted resource record set.
        - You can't create latency, failover, or geolocation resource record sets that have the
          same values for the Name and Type elements as weighted resource record sets.
        - You can create a maximum of 100 weighted resource record sets that have the same values
          for the Name and Type elements.
        - For weighted (but not weighted alias) resource record sets, if you set Weight to 0 for a
          resource record set, Amazon Route 53 never responds to queries with the applicable value
          for that resource record set.  However, if you set Weight to 0 for all resource record
          sets that have the same combination of DNS name and type, traffic is routed to all
          resources with equal probability.  The effect of setting Weight to 0 is different when
          you associate health checks with weighted resource record sets. For more information,
          see `Options for Configuring Amazon Route 53 Active-Active and Active-Passive Failover`__
          in the Amazon Route 53 Developer Guide.

          .. __: http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-configuring-options.html

    Region
        Valid for Latency-based resource record sets only.  The Amazon EC2 Region where the resource
        that is specified in this resource record set resides. The resource typically is an AWS
        resource, such as an EC2 instance or an ELB load balancer, and is referred to by an IP
        address or a DNS domain name, depending on the record type.

    GeoLocation
        Geo location resource record sets only.  A dict that lets you control how Route 53 responds
        to DNS queries based on the geographic origin of the query.  For example, if you want all
        queries from Africa to be routed to a web server with an IP address of 192.0.2.111, create a
        resource record set with a Type of A and a ContinentCode of AF.

        .. code-block:: text

            ContinentCode
                The two-letter code for the continent.
                Valid values: AF | AN | AS | EU | OC | NA | SA
                Constraint: Specifying ContinentCode with either CountryCode or SubdivisionCode
                            returns an InvalidInput error.
            CountryCode
                The two-letter code for the country.
            SubdivisionCode
                The code for the subdivision, for example, a state in the United States or a
                province in Canada.

        Notes

        - Creating geolocation and geolocation alias resource record sets in private hosted zones
          is not supported.
        - If you create separate resource record sets for overlapping geographic regions (for
          example, one resource record set for a continent and one for a country on the same
          continent), priority goes to the smallest geographic region. This allows you to route
          most queries for a continent to one resource and to route queries for a country on that
          continent to a different resource.
        - You can't create two geolocation resource record sets that specify the same geographic
          location.
        - The value ``*`` in the CountryCode element matches all geographic locations that aren't
          specified in other geolocation resource record sets that have the same values for the
          Name and Type elements.
        - Geolocation works by mapping IP addresses to locations.  However, some IP addresses
          aren't mapped to geographic locations, so even if you create geolocation resource
          record sets that cover all seven continents, Amazon Route 53 will receive some DNS
          queries from locations that it can't identify.  We recommend that you
          create a resource record set for which the value of CountryCode is
          ``*``, which handles both queries that come from locations for which you
          haven't created geolocation resource record sets and queries from IP
          addresses that aren't mapped to a location.  If you don't create a ``*``
          resource record set, Amazon Route 53 returns a "no answer" response
          for queries from those locations.
        - You can't create non-geolocation resource record sets that have the same values for the
          Name and Type elements as geolocation resource record sets.

    TTL
        The resource record cache time to live (TTL), in seconds.
        Note the following:

        - If you're creating an alias resource record set, omit TTL. Amazon Route 53 uses the
          value of TTL for the alias target.
        - If you're associating this resource record set with a health check (if you're adding
          a HealthCheckId element), we recommend that you specify a TTL of 60 seconds or less so
          clients respond quickly to changes in health status.
        - All of the resource record sets in a group of weighted, latency, geolocation, or
          failover resource record sets must have the same value for TTL.
        - If a group of weighted resource record sets includes one or more weighted alias
          resource record sets for which the alias target is an ELB load balancer, we recommend
          that you specify a TTL of 60 seconds for all of the non-alias weighted resource record
          sets that have the same name and type. Values other than 60 seconds (the TTL for load
          balancers) will change the effect of the values that you specify for Weight.

    ResourceRecords
        A list, containing one or more values for the resource record.  No single value can exceed
        4,000 characters.  For details on how to format values for different record types, see
        `Supported DNS Resource Record Types`__ in the Amazon Route 53 Developer Guide.

        .. __: http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/ResourceRecordTypes.html

        Note:  You can specify more than one value for all record types except CNAME and SOA.

        It is also possible to pass "magic" strings as resource record values.  This functionality
        can easily be extended, but for the moment supports the following:

            'magic:ec2_instance_tag:some_tag_name:some_string:some_instance_attr'

        This tells salt to lookup an EC2 instance with a tag 'some_tag_name' which has the value
        'some_string' and substitute the 'some_instance_attr' attribute of that instance as the
        resource record value being evaluated.

        This should work generally for any EC2 instance tags, as long as the instance attribute
        being fetched is available to getattr(instance, 'attribute') as seen in the code below.
        Anything else will most likely require this function to be extended to handle it.

        The canonical use-case for this (at least at our site) is to query the Name tag (which
        we always populate with the host's FQDN) to lookup the public or private IPs bound to the
        instance, so we can then automgically create Route 53 records for them.

    AliasTarget
        The rules governing how to define an AliasTarget for the various supported use-cases are
        obtuse beyond reason and attempting to paraphrase them (or even worse, cut-and-paste them
        in their entirety) would be silly and counterproductive.  If you need this feature, then
        Read The Fine Materials at the `Boto 3 Route 53 page`__ and/or the `AWS Route 53 docs`__
        and suss them for yourself - I sure won't claim to understand them partcularly well.

        .. __: http://boto3.readthedocs.io/en/latest/reference/services/route53.html#Route53.Client.change_resource_record_sets
        .. __: http://docs.aws.amazon.com/Route53/latest/APIReference/API_AliasTarget.html

    region
        The region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.
    """
    Name = Name if Name else name

    if Type is None:
        raise SaltInvocationError(
            "'Type' is a required parameter when adding or updating resource records."
        )
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    args = {
        "Id": HostedZoneId,
        "Name": DomainName,
        "PrivateZone": PrivateZone,
        "region": region,
        "key": key,
        "keyid": keyid,
        "profile": profile,
    }
    zone = __salt__["boto3_route53.find_hosted_zone"](**args)
    if not zone:
        ret["comment"] = "Route 53 {} hosted zone {} not found".format(
            "private" if PrivateZone else "public", DomainName
        )
        log.info(ret["comment"])
        return ret
    zone = zone[0]
    HostedZoneId = zone["HostedZone"]["Id"]

    # Convert any magic RR values to something AWS will understand, and otherwise clean them up.
    fixed_rrs = []
    if ResourceRecords:
        for rr in ResourceRecords:
            if rr.startswith("magic:"):
                fields = rr.split(":")
                if fields[1] == "ec2_instance_tag":
                    if len(fields) != 5:
                        log.warning(
                            "Invalid magic RR value seen: '%s'.  Passing as-is.", rr
                        )
                        fixed_rrs += [rr]
                        continue
                    tag_name = fields[2]
                    tag_value = fields[3]
                    instance_attr = fields[4]
                    good_states = (
                        "pending",
                        "rebooting",
                        "running",
                        "stopping",
                        "stopped",
                    )
                    r = __salt__["boto_ec2.find_instances"](
                        tags={tag_name: tag_value},
                        return_objs=True,
                        in_states=good_states,
                        region=region,
                        key=key,
                        keyid=keyid,
                        profile=profile,
                    )
                    if len(r) < 1:
                        ret["comment"] = (
                            "No EC2 instance with tag {} == {} found".format(
                                tag_name, tag_value
                            )
                        )
                        log.error(ret["comment"])
                        ret["result"] = False
                        return ret
                    if len(r) > 1:
                        ret["comment"] = (
                            "Multiple EC2 instances with tag {} == {} found".format(
                                tag_name, tag_value
                            )
                        )
                        log.error(ret["comment"])
                        ret["result"] = False
                        return ret
                    instance = r[0]
                    res = getattr(instance, instance_attr, None)
                    if res:
                        log.debug(
                            "Found %s %s for instance %s",
                            instance_attr,
                            res,
                            instance.id,
                        )
                        fixed_rrs += [__salt__["boto3_route53.aws_encode"](res)]
                    else:
                        ret["comment"] = "Attribute {} not found on instance {}".format(
                            instance_attr, instance.id
                        )
                        log.error(ret["comment"])
                        ret["result"] = False
                        return ret
                else:
                    ret["comment"] = (
                        "Unknown RR magic value seen: {}.  Please extend the "
                        "boto3_route53 state module to add support for your preferred "
                        "incantation.".format(fields[1])
                    )
                    log.error(ret["comment"])
                    ret["result"] = False
                    return ret
            else:
                # for TXT records the entry must be encapsulated in quotes as required by the API
                # this appears to be incredibly difficult with the jinja templating engine
                # so inject the quotations here to make a viable ChangeBatch
                if Type == "TXT":
                    rr = f'"{rr}"'
                fixed_rrs += [rr]
        ResourceRecords = [{"Value": rr} for rr in sorted(fixed_rrs)]

    recordsets = __salt__["boto3_route53.get_resource_records"](
        HostedZoneId=HostedZoneId,
        StartRecordName=Name,
        StartRecordType=Type,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )

    if SetIdentifier and recordsets:
        log.debug(
            "Filter recordsets %s by SetIdentifier %s.", recordsets, SetIdentifier
        )
        recordsets = [r for r in recordsets if r.get("SetIdentifier") == SetIdentifier]
        log.debug("Resulted in recordsets %s.", recordsets)

    create = False
    update = False
    updatable = [
        "SetIdentifier",
        "Weight",
        "Region",
        "GeoLocation",
        "Failover",
        "TTL",
        "AliasTarget",
        "HealthCheckId",
        "TrafficPolicyInstanceId",
    ]
    if not recordsets:
        create = True
        if __opts__["test"]:
            ret["comment"] = (
                "Route 53 resource record {} with type {} would be added.".format(
                    Name, Type
                )
            )
            ret["result"] = None
            return ret
    elif len(recordsets) > 1:
        ret["comment"] = "Given criteria matched more than one ResourceRecordSet."
        log.error(ret["comment"])
        ret["result"] = False
        return ret
    else:
        rrset = recordsets[0]
        for u in updatable:
            if locals().get(u) != rrset.get(u):
                update = True
                break
        if rrset.get("ResourceRecords") is not None:
            if ResourceRecords != sorted(
                rrset.get("ResourceRecords"), key=lambda x: x["Value"]
            ):
                update = True
        elif (AliasTarget is not None) and (rrset.get("AliasTarget") is not None):
            if sorted(AliasTarget) != sorted(rrset.get("AliasTarget")):
                update = True

    if not create and not update:
        ret["comment"] = (
            "Route 53 resource record {} with type {} is already in the desired state."
            "".format(Name, Type)
        )
        log.info(ret["comment"])
        return ret
    else:
        if __opts__["test"]:
            ret["comment"] = (
                "Route 53 resource record {} with type {} would be updated.".format(
                    Name, Type
                )
            )
            ret["result"] = None
            return ret
        ResourceRecordSet = {"Name": Name, "Type": Type}
        if ResourceRecords:
            ResourceRecordSet["ResourceRecords"] = ResourceRecords
        for u in updatable:
            if locals().get(u) or (locals().get(u) == 0):
                ResourceRecordSet.update({u: locals().get(u)})
            else:
                log.debug(
                    "Not updating ResourceRecordSet with local value: %s",
                    locals().get(u),
                )

        ChangeBatch = {
            "Changes": [{"Action": "UPSERT", "ResourceRecordSet": ResourceRecordSet}]
        }

        if __salt__["boto3_route53.change_resource_record_sets"](
            HostedZoneId=HostedZoneId,
            ChangeBatch=ChangeBatch,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        ):
            ret["comment"] = "Route 53 resource record {} with type {} {}.".format(
                Name, Type, "created" if create else "updated"
            )
            log.info(ret["comment"])
            if create:
                ret["changes"]["old"] = None
            else:
                ret["changes"]["old"] = rrset
            ret["changes"]["new"] = ResourceRecordSet
        else:
            ret["comment"] = (
                "Failed to {} Route 53 resource record {} with type {}.".format(
                    "create" if create else "update", Name, Type
                )
            )
            log.error(ret["comment"])
            ret["result"] = False

    return ret


def rr_absent(
    name,
    HostedZoneId=None,
    DomainName=None,
    PrivateZone=False,
    Name=None,
    Type=None,
    SetIdentifier=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure the Route53 record is deleted.

    name
        The name of the state definition.  This will be used for Name if the latter is
        not provided.

    HostedZoneId
        The ID of the zone to delete the record from.  Exclusive with DomainName.

    DomainName
        The domain name of the zone to delete the record from.  Exclusive with HostedZoneId.

    PrivateZone
        Set to True if the RR to be removed is in a private zone, False if public.

    Name
        Name of the resource record.

    Type
        The record type (A, NS, MX, TXT, etc.)

    SetIdentifier
        Valid for Weighted, Latency, Geolocation, and Failover resource record sets only.
        An identifier that differentiates among multiple resource record sets that have the same
        combination of DNS name and type.  The value of SetIdentifier must be unique for each
        resource record set that has the same combination of DNS name and type. Omit SetIdentifier
        for any other types of record sets.

    region
        The region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.
    """
    Name = Name if Name else name

    if Type is None:
        raise SaltInvocationError(
            "'Type' is a required parameter when deleting resource records."
        )
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    args = {
        "Id": HostedZoneId,
        "Name": DomainName,
        "PrivateZone": PrivateZone,
        "region": region,
        "key": key,
        "keyid": keyid,
        "profile": profile,
    }
    zone = __salt__["boto3_route53.find_hosted_zone"](**args)
    if not zone:
        ret["comment"] = "Route 53 {} hosted zone {} not found".format(
            "private" if PrivateZone else "public", DomainName
        )
        log.info(ret["comment"])
        return ret
    zone = zone[0]
    HostedZoneId = zone["HostedZone"]["Id"]

    recordsets = __salt__["boto3_route53.get_resource_records"](
        HostedZoneId=HostedZoneId,
        StartRecordName=Name,
        StartRecordType=Type,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if SetIdentifier and recordsets:
        log.debug(
            "Filter recordsets %s by SetIdentifier %s.", recordsets, SetIdentifier
        )
        recordsets = [r for r in recordsets if r.get("SetIdentifier") == SetIdentifier]
        log.debug("Resulted in recordsets %s.", recordsets)
    if not recordsets:
        ret["comment"] = (
            "Route 53 resource record {} with type {} already absent.".format(
                Name, Type
            )
        )
        return ret
    elif len(recordsets) > 1:
        ret["comment"] = "Given criteria matched more than one ResourceRecordSet."
        log.error(ret["comment"])
        ret["result"] = False
        return ret
    ResourceRecordSet = recordsets[0]
    if __opts__["test"]:
        ret["comment"] = (
            "Route 53 resource record {} with type {} would be deleted.".format(
                Name, Type
            )
        )
        ret["result"] = None
        return ret

    ChangeBatch = {
        "Changes": [{"Action": "DELETE", "ResourceRecordSet": ResourceRecordSet}]
    }

    if __salt__["boto3_route53.change_resource_record_sets"](
        HostedZoneId=HostedZoneId,
        ChangeBatch=ChangeBatch,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    ):
        ret["comment"] = "Route 53 resource record {} with type {} deleted.".format(
            Name, Type
        )
        log.info(ret["comment"])
        ret["changes"]["old"] = ResourceRecordSet
        ret["changes"]["new"] = None
    else:
        ret["comment"] = (
            "Failed to delete Route 53 resource record {} with type {}.".format(
                Name, Type
            )
        )
        log.error(ret["comment"])
        ret["result"] = False

    return ret

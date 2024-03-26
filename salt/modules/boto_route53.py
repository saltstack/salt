"""
Connection module for Amazon Route53

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit route53 credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: yaml

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        route53.keyid: GKTADJGHEIQSXMKKRBJ08H
        route53.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        route53.region: us-east-1

    If a region is not specified, the default is 'universal', which is what the boto_route53
    library expects, rather than None.

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
import time

import salt.utils.compat
import salt.utils.odict as odict
import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

try:
    # pylint: disable=unused-import
    import boto
    import boto.route53
    import boto.route53.healthcheck
    from boto.route53.exception import DNSServerError

    # pylint: enable=unused-import
    logging.getLogger("boto").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    # create_zone params were changed in boto 2.35+
    return salt.utils.versions.check_boto_reqs(boto_ver="2.35.0", check_boto3=False)


def __init__(opts):
    if HAS_BOTO:
        __utils__["boto.assign_funcs"](__name__, "route53", pack=__salt__)


def _get_split_zone(zone, _conn, private_zone):
    """
    With boto route53, zones can only be matched by name
    or iterated over in a list.  Since the name will be the
    same for public and private zones in a split DNS situation,
    iterate over the list and match the zone name and public/private
    status.
    """
    for _zone in _conn.get_zones():
        if _zone.name == zone:
            _private_zone = (
                True if _zone.config["PrivateZone"].lower() == "true" else False
            )
            if _private_zone == private_zone:
                return _zone
    return False


def _is_retryable_error(exception):
    return exception.code not in ["SignatureDoesNotMatch"]


def describe_hosted_zones(
    zone_id=None, domain_name=None, region=None, key=None, keyid=None, profile=None
):
    """
    Return detailed info about one, or all, zones in the bound account.
    If neither zone_id nor domain_name is provided, return all zones.
    Note that the return format is slightly different between the 'all'
    and 'single' description types.

    zone_id
        The unique identifier for the Hosted Zone

    domain_name
        The FQDN of the Hosted Zone (including final period)

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.describe_hosted_zones domain_name=foo.bar.com. \
                profile='{"region": "us-east-1", "keyid": "A12345678AB", "key": "xblahblahblah"}'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if zone_id and domain_name:
        raise SaltInvocationError(
            "At most one of zone_id or domain_name may be provided"
        )
    retries = 10
    while retries:
        try:
            if zone_id:
                zone_id = (
                    zone_id.replace("/hostedzone/", "")
                    if zone_id.startswith("/hostedzone/")
                    else zone_id
                )
                ret = getattr(
                    conn.get_hosted_zone(zone_id), "GetHostedZoneResponse", None
                )
            elif domain_name:
                ret = getattr(
                    conn.get_hosted_zone_by_name(domain_name),
                    "GetHostedZoneResponse",
                    None,
                )
            else:
                marker = None
                ret = None
                while marker != "":
                    r = conn.get_all_hosted_zones(start_marker=marker, zone_list=ret)
                    ret = r["ListHostedZonesResponse"]["HostedZones"]
                    marker = r["ListHostedZonesResponse"].get("NextMarker", "")
            return ret if ret else []
        except DNSServerError as e:
            if retries:
                if "Throttling" == e.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == e.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request."
                    )
                time.sleep(3)
                retries -= 1
                continue
            log.error("Could not list zones: %s", e.message)
            return []


def list_all_zones_by_name(region=None, key=None, keyid=None, profile=None):
    """
    List, by their FQDNs, all hosted zones in the bound account.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.list_all_zones_by_name
    """
    ret = describe_hosted_zones(region=region, key=key, keyid=keyid, profile=profile)
    return [r["Name"] for r in ret]


def list_all_zones_by_id(region=None, key=None, keyid=None, profile=None):
    """
    List, by their IDs, all hosted zones in the bound account.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.list_all_zones_by_id
    """
    ret = describe_hosted_zones(region=region, key=key, keyid=keyid, profile=profile)
    return [r["Id"].replace("/hostedzone/", "") for r in ret]


def zone_exists(
    zone,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    retry_on_rate_limit=None,
    rate_limit_retries=None,
    retry_on_errors=True,
    error_retries=5,
):
    """
    Check for the existence of a Route53 hosted zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.zone_exists example.org

    retry_on_errors
        Continue to query if the zone exists after an error is
        raised. The previously used argument `retry_on_rate_limit`
        was deprecated for this argument. Users can still use
        `retry_on_rate_limit` to ensure backwards compatibility,
        but please migrate to using the favored `retry_on_errors`
        argument instead.

    error_retries
        Number of times to attempt to query if the zone exists.
        The previously used argument `rate_limit_retries` was
        deprecated for this arguments. Users can still use
        `rate_limit_retries` to ensure backwards compatibility,
        but please migrate to using the favored `error_retries`
        argument instead.
    """
    if region is None:
        region = "universal"

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if retry_on_rate_limit or rate_limit_retries is not None:
        if retry_on_rate_limit is not None:
            retry_on_errors = retry_on_rate_limit
        if rate_limit_retries is not None:
            error_retries = rate_limit_retries

    while error_retries > 0:
        try:
            return bool(conn.get_zone(zone))

        except DNSServerError as e:
            if retry_on_errors and _is_retryable_error(e):
                if "Throttling" == e.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == e.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request "
                    )
                time.sleep(3)
                error_retries -= 1
                continue
            raise
    return False


def create_zone(
    zone,
    private=False,
    vpc_id=None,
    vpc_region=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create a Route53 hosted zone.

    .. versionadded:: 2015.8.0

    zone
        DNS zone to create

    private
        True/False if the zone will be a private zone

    vpc_id
        VPC ID to associate the zone to (required if private is True)

    vpc_region
        VPC Region (required if private is True)

    region
        region endpoint to connect to

    key
        AWS key

    keyid
        AWS keyid

    profile
        AWS pillar profile

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.create_zone example.org
    """
    if region is None:
        region = "universal"

    if private:
        if not vpc_id or not vpc_region:
            msg = "vpc_id and vpc_region must be specified for a private zone"
            raise SaltInvocationError(msg)

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    _zone = conn.get_zone(zone)

    if _zone:
        return False

    conn.create_zone(zone, private_zone=private, vpc_id=vpc_id, vpc_region=vpc_region)
    return True


def create_healthcheck(
    ip_addr=None,
    fqdn=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    port=53,
    hc_type="TCP",
    resource_path="",
    string_match=None,
    request_interval=30,
    failure_threshold=3,
    retry_on_errors=True,
    error_retries=5,
):
    """
    Create a Route53 healthcheck

    .. versionadded:: 2018.3.0

    ip_addr

        IP address to check.  ip_addr or fqdn is required.

    fqdn

        Domain name of the endpoint to check.  ip_addr or fqdn is required

    port

        Port to check

    hc_type

        Healthcheck type.  HTTP | HTTPS | HTTP_STR_MATCH | HTTPS_STR_MATCH | TCP

    resource_path

        Path to check

    string_match

        If hc_type is HTTP_STR_MATCH or HTTPS_STR_MATCH, the string to search for in the
        response body from the specified resource

    request_interval

        The number of seconds between the time that Amazon Route 53 gets a response from
        your endpoint and the time that it sends the next health-check request.

    failure_threshold

        The number of consecutive health checks that an endpoint must pass or fail for
        Amazon Route 53 to change the current status of the endpoint from unhealthy to
        healthy or vice versa.

    region

        Region endpoint to connect to

    key

        AWS key

    keyid

        AWS keyid

    profile

        AWS pillar profile

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.create_healthcheck 192.168.0.1
        salt myminion boto_route53.create_healthcheck 192.168.0.1 port=443 hc_type=HTTPS \
                                                      resource_path=/ fqdn=blog.saltstack.furniture
    """
    if fqdn is None and ip_addr is None:
        msg = "One of the following must be specified: fqdn or ip_addr"
        log.error(msg)
        return {"error": msg}
    hc_ = boto.route53.healthcheck.HealthCheck(
        ip_addr,
        port,
        hc_type,
        resource_path,
        fqdn=fqdn,
        string_match=string_match,
        request_interval=request_interval,
        failure_threshold=failure_threshold,
    )

    if region is None:
        region = "universal"

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    while error_retries > 0:
        try:
            return {"result": conn.create_health_check(hc_)}
        except DNSServerError as exc:
            log.debug(exc)
            if retry_on_errors and _is_retryable_error(exc):
                if "Throttling" == exc.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == exc.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request."
                    )
                time.sleep(3)
                error_retries -= 1
                continue
            return {"error": __utils__["boto.get_error"](exc)}
    return False


def delete_zone(zone, region=None, key=None, keyid=None, profile=None):
    """
    Delete a Route53 hosted zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.delete_zone example.org
    """
    if region is None:
        region = "universal"

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    _zone = conn.get_zone(zone)

    if _zone:
        conn.delete_hosted_zone(_zone.id)
        return True
    return False


def _encode_name(name):
    return name.replace("*", r"\052")


def _decode_name(name):
    return name.replace(r"\052", "*")


def get_record(
    name,
    zone,
    record_type,
    fetch_all=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    split_dns=False,
    private_zone=False,
    identifier=None,
    retry_on_rate_limit=None,
    rate_limit_retries=None,
    retry_on_errors=True,
    error_retries=5,
):
    """
    Get a record from a zone.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.get_record test.example.org example.org A

    retry_on_errors
        Continue to query if the zone exists after an error is
        raised. The previously used argument `retry_on_rate_limit`
        was deprecated for this argument. Users can still use
        `retry_on_rate_limit` to ensure backwards compatibility,
        but please migrate to using the favored `retry_on_errors`
        argument instead.

    error_retries
        Number of times to attempt to query if the zone exists.
        The previously used argument `rate_limit_retries` was
        deprecated for this arguments. Users can still use
        `rate_limit_retries` to ensure backwards compatibility,
        but please migrate to using the favored `error_retries`
        argument instead.
    """
    if region is None:
        region = "universal"

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if retry_on_rate_limit or rate_limit_retries is not None:
        if retry_on_rate_limit is not None:
            retry_on_errors = retry_on_rate_limit
        if rate_limit_retries is not None:
            error_retries = rate_limit_retries

    _record = None
    ret = odict.OrderedDict()
    while error_retries > 0:
        try:
            if split_dns:
                _zone = _get_split_zone(zone, conn, private_zone)
            else:
                _zone = conn.get_zone(zone)
            if not _zone:
                msg = f"Failed to retrieve zone {zone}"
                log.error(msg)
                return None
            _type = record_type.upper()

            name = _encode_name(name)

            _record = _zone.find_records(
                name, _type, all=fetch_all, identifier=identifier
            )

            break  # the while True

        except DNSServerError as e:
            if retry_on_errors and _is_retryable_error(e):
                if "Throttling" == e.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == e.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request."
                    )
                time.sleep(3)
                error_retries -= 1
                continue
            raise

    if _record:
        ret["name"] = _decode_name(_record.name)
        ret["value"] = _record.resource_records[0]
        ret["record_type"] = _record.type
        ret["ttl"] = _record.ttl
        if _record.identifier:
            ret["identifier"] = []
            ret["identifier"].append(_record.identifier)
            ret["identifier"].append(_record.weight)

    return ret


def _munge_value(value, _type):
    split_types = ["A", "MX", "AAAA", "TXT", "SRV", "SPF", "NS"]
    if _type in split_types:
        return value.split(",")
    return value


def add_record(
    name,
    value,
    zone,
    record_type,
    identifier=None,
    ttl=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    wait_for_sync=True,
    split_dns=False,
    private_zone=False,
    retry_on_rate_limit=None,
    rate_limit_retries=None,
    retry_on_errors=True,
    error_retries=5,
):
    """
    Add a record to a zone.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.add_record test.example.org 1.1.1.1 example.org A

    retry_on_errors
        Continue to query if the zone exists after an error is
        raised. The previously used argument `retry_on_rate_limit`
        was deprecated for this argument. Users can still use
        `retry_on_rate_limit` to ensure backwards compatibility,
        but please migrate to using the favored `retry_on_errors`
        argument instead.

    error_retries
        Number of times to attempt to query if the zone exists.
        The previously used argument `rate_limit_retries` was
        deprecated for this arguments. Users can still use
        `rate_limit_retries` to ensure backwards compatibility,
        but please migrate to using the favored `error_retries`
        argument instead.
    """
    if region is None:
        region = "universal"

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if retry_on_rate_limit or rate_limit_retries is not None:
        if retry_on_rate_limit is not None:
            retry_on_errors = retry_on_rate_limit
        if rate_limit_retries is not None:
            error_retries = rate_limit_retries

    while error_retries > 0:
        try:
            if split_dns:
                _zone = _get_split_zone(zone, conn, private_zone)
            else:
                _zone = conn.get_zone(zone)
            if not _zone:
                msg = f"Failed to retrieve zone {zone}"
                log.error(msg)
                return False
            _type = record_type.upper()
            break

        except DNSServerError as e:
            if retry_on_errors and _is_retryable_error(e):
                if "Throttling" == e.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == e.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request."
                    )
                time.sleep(3)
                error_retries -= 1
                continue
            raise

    _value = _munge_value(value, _type)
    while error_retries > 0:
        try:
            # add_record requires a ttl value, annoyingly.
            if ttl is None:
                ttl = 60
            status = _zone.add_record(_type, name, _value, ttl, identifier)
            return _wait_for_sync(status.id, conn, wait_for_sync)

        except DNSServerError as e:
            if retry_on_errors and _is_retryable_error(e):
                if "Throttling" == e.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == e.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request."
                    )
                time.sleep(3)
                error_retries -= 1
                continue
            raise
    return False


def update_record(
    name,
    value,
    zone,
    record_type,
    identifier=None,
    ttl=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    wait_for_sync=True,
    split_dns=False,
    private_zone=False,
    retry_on_rate_limit=None,
    rate_limit_retries=None,
    retry_on_errors=True,
    error_retries=5,
):
    """
    Modify a record in a zone.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.modify_record test.example.org 1.1.1.1 example.org A

    retry_on_errors
        Continue to query if the zone exists after an error is
        raised. The previously used argument `retry_on_rate_limit`
        was deprecated for this argument. Users can still use
        `retry_on_rate_limit` to ensure backwards compatibility,
        but please migrate to using the favored `retry_on_errors`
        argument instead.

    error_retries
        Number of times to attempt to query if the zone exists.
        The previously used argument `rate_limit_retries` was
        deprecated for this arguments. Users can still use
        `rate_limit_retries` to ensure backwards compatibility,
        but please migrate to using the favored `error_retries`
        argument instead.
    """
    if region is None:
        region = "universal"

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if split_dns:
        _zone = _get_split_zone(zone, conn, private_zone)
    else:
        _zone = conn.get_zone(zone)
    if not _zone:
        msg = f"Failed to retrieve zone {zone}"
        log.error(msg)
        return False
    _type = record_type.upper()

    if retry_on_rate_limit or rate_limit_retries is not None:
        if retry_on_rate_limit is not None:
            retry_on_errors = retry_on_rate_limit
        if rate_limit_retries is not None:
            error_retries = rate_limit_retries

    _value = _munge_value(value, _type)
    while error_retries > 0:
        try:
            old_record = _zone.find_records(name, _type, identifier=identifier)
            if not old_record:
                return False
            status = _zone.update_record(old_record, _value, ttl, identifier)
            return _wait_for_sync(status.id, conn, wait_for_sync)

        except DNSServerError as e:
            if retry_on_errors and _is_retryable_error(e):
                if "Throttling" == e.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == e.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request."
                    )
                time.sleep(3)
                error_retries -= 1
                continue
            raise
    return False


def delete_record(
    name,
    zone,
    record_type,
    identifier=None,
    all_records=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    wait_for_sync=True,
    split_dns=False,
    private_zone=False,
    retry_on_rate_limit=None,
    rate_limit_retries=None,
    retry_on_errors=True,
    error_retries=5,
):
    """
    Modify a record in a zone.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.delete_record test.example.org example.org A

    retry_on_errors
        Continue to query if the zone exists after an error is
        raised. The previously used argument `retry_on_rate_limit`
        was deprecated for this argument. Users can still use
        `retry_on_rate_limit` to ensure backwards compatibility,
        but please migrate to using the favored `retry_on_errors`
        argument instead.

    error_retries
        Number of times to attempt to query if the zone exists.
        The previously used argument `rate_limit_retries` was
        deprecated for this arguments. Users can still use
        `rate_limit_retries` to ensure backwards compatibility,
        but please migrate to using the favored `error_retries`
        argument instead.
    """
    if region is None:
        region = "universal"

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if split_dns:
        _zone = _get_split_zone(zone, conn, private_zone)
    else:
        _zone = conn.get_zone(zone)
    if not _zone:
        msg = f"Failed to retrieve zone {zone}"
        log.error(msg)
        return False
    _type = record_type.upper()

    if retry_on_rate_limit or rate_limit_retries is not None:
        if retry_on_rate_limit is not None:
            retry_on_errors = retry_on_rate_limit
        if rate_limit_retries is not None:
            error_retries = rate_limit_retries

    while error_retries > 0:
        try:
            old_record = _zone.find_records(
                name, _type, all=all_records, identifier=identifier
            )
            if not old_record:
                return False
            status = _zone.delete_record(old_record)
            return _wait_for_sync(status.id, conn, wait_for_sync)

        except DNSServerError as e:
            if retry_on_errors and _is_retryable_error(e):
                if "Throttling" == e.code:
                    log.debug("Throttled by AWS API.")
                elif "PriorRequestNotComplete" == e.code:
                    log.debug(
                        "The request was rejected by AWS API. "
                        "Route 53 was still processing a prior request."
                    )
                time.sleep(3)
                error_retries -= 1
                continue
            raise


def _try_func(conn, func, **args):
    tries = 30
    while True:
        try:
            return getattr(conn, func)(**args)
        except AttributeError as e:
            # Don't include **args in log messages - security concern.
            log.error(
                "Function `%s()` not found for AWS connection object %s", func, conn
            )
            return None
        except DNSServerError as e:
            if tries and e.code == "Throttling":
                log.debug("Throttled by AWS API.  Will retry in 5 seconds")
                time.sleep(5)
                tries -= 1
                continue
            log.error("Failed calling %s(): %s", func, e)
            return None


def _wait_for_sync(status, conn, wait=True):
    ### Wait should be a bool or an integer
    if wait is True:
        wait = 600
    if not wait:
        return True
    orig_wait = wait
    log.info("Waiting up to %s seconds for Route53 changes to synchronize", orig_wait)
    while wait > 0:
        change = conn.get_change(status)
        current = change.GetChangeResponse.ChangeInfo.Status
        if current == "INSYNC":
            return True
        sleep = wait if wait % 60 == wait else 60
        log.info(
            "Sleeping %s seconds waiting for changes to synch (current status %s)",
            sleep,
            current,
        )
        time.sleep(sleep)
        wait -= sleep
        continue
    log.error("Route53 changes not synced after %s seconds.", orig_wait)
    return False


def create_hosted_zone(
    domain_name,
    caller_ref=None,
    comment="",
    private_zone=False,
    vpc_id=None,
    vpc_name=None,
    vpc_region=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create a new Route53 Hosted Zone. Returns a Python data structure with information about the
    newly created Hosted Zone.

    domain_name
        The name of the domain. This must be fully-qualified, terminating with a period.  This is
        the name you have registered with your domain registrar.  It is also the name you will
        delegate from your registrar to the Amazon Route 53 delegation servers returned in response
        to this request.

    caller_ref
        A unique string that identifies the request and that allows create_hosted_zone() calls to
        be retried without the risk of executing the operation twice.  It can take several minutes
        for the change to replicate globally, and change from PENDING to INSYNC status. Thus it's
        best to provide some value for this where possible, since duplicate calls while the first
        is in PENDING status will be accepted and can lead to multiple copies of the zone being
        created.  On the other hand, if a zone is created with a given caller_ref, then deleted,
        a second attempt to create a zone with the same caller_ref will fail until that caller_ref
        is flushed from the Route53 system, which can take upwards of 24 hours.

    comment
        Any comments you want to include about the hosted zone.

    private_zone
        Set True if creating a private hosted zone.

    vpc_id
        When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with vpe_name.  Ignored when creating a non-private zone.

    vpc_name
        When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with vpe_id.  Ignored when creating a non-private zone.

    vpc_region
        When creating a private hosted zone, the region of the associated VPC is required.  If not
        provided, an effort will be made to determine it from vpc_id or vpc_name, where possible.
        If this fails, you'll need to provide an explicit value for this option.  Ignored when
        creating a non-private zone.

    region
        Region endpoint to connect to.

    key
        AWS key to bind with.

    keyid
        AWS keyid to bind with.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.create_hosted_zone example.org
    """
    if region is None:
        region = "universal"

    if not domain_name.endswith("."):
        raise SaltInvocationError(
            "Domain MUST be fully-qualified, complete with ending period."
        )

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    deets = conn.get_hosted_zone_by_name(domain_name)
    if deets:
        log.info("Route53 hosted zone %s already exists", domain_name)
        return None

    args = {
        "domain_name": domain_name,
        "caller_ref": caller_ref,
        "comment": comment,
        "private_zone": private_zone,
    }

    if private_zone:
        if not _exactly_one((vpc_name, vpc_id)):
            raise SaltInvocationError(
                "Either vpc_name or vpc_id is required when creating a private zone."
            )
        vpcs = __salt__["boto_vpc.describe_vpcs"](
            vpc_id=vpc_id,
            name=vpc_name,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        ).get("vpcs", [])
        if vpc_region and vpcs:
            vpcs = [v for v in vpcs if v["region"] == vpc_region]
        if not vpcs:
            log.error(
                "Private zone requested but a VPC matching given criteria not found."
            )
            return None
        if len(vpcs) > 1:
            log.error(
                "Private zone requested but multiple VPCs matching given "
                "criteria found: %s.",
                [v["id"] for v in vpcs],
            )
            return None
        vpc = vpcs[0]
        if vpc_name:
            vpc_id = vpc["id"]
        if not vpc_region:
            vpc_region = vpc["region"]
        args.update({"vpc_id": vpc_id, "vpc_region": vpc_region})
    else:
        if any((vpc_id, vpc_name, vpc_region)):
            log.info(
                "Options vpc_id, vpc_name, and vpc_region are ignored "
                "when creating non-private zones."
            )

    r = _try_func(conn, "create_hosted_zone", **args)
    if r is None:
        log.error("Failed to create hosted zone %s", domain_name)
        return None
    r = r.get("CreateHostedZoneResponse", {})
    # Pop it since it'll be irrelevant by the time we return
    status = r.pop("ChangeInfo", {}).get("Id", "").replace("/change/", "")
    synced = _wait_for_sync(status, conn, wait=600)
    if not synced:
        log.error("Hosted zone %s not synced after 600 seconds.", domain_name)
        return None
    return r

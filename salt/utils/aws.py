"""
Connection library for AWS

.. versionadded:: 2015.5.0

This is a base library used by a number of AWS services.

:depends: requests
"""

import binascii
import copy
import hashlib
import hmac
import logging
import random
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

import salt.config
import salt.utils.hashutils
import salt.utils.xmlutil as xml

log = logging.getLogger(__name__)

DEFAULT_LOCATION = "us-east-1"
DEFAULT_AWS_API_VERSION = "2016-11-15"
AWS_RETRY_CODES = [
    "RequestLimitExceeded",
    "InsufficientInstanceCapacity",
    "InternalError",
    "Unavailable",
    "InsufficientAddressCapacity",
    "InsufficientReservedInstanceCapacity",
]
AWS_METADATA_TIMEOUT = 3.05

AWS_MAX_RETRIES = 7

IROLE_CODE = "use-instance-role-credentials"
__AccessKeyId__ = ""
__SecretAccessKey__ = ""
__Token__ = ""
__Expiration__ = ""
__Location__ = ""
__AssumeCache__ = {}
__IMDS_Token__ = None


def sleep_exponential_backoff(attempts):
    """
    backoff an exponential amount of time to throttle requests
    during "API Rate Exceeded" failures as suggested by the AWS documentation here:
    https://docs.aws.amazon.com/AWSEC2/latest/APIReference/query-api-troubleshooting.html
    and also here:
    https://docs.aws.amazon.com/general/latest/gr/api-retries.html
    Failure to implement this approach results in a failure rate of >30% when using salt-cloud with
    "--parallel" when creating 50 or more instances with a fixed delay of 2 seconds.
    A failure rate of >10% is observed when using the salt-api with an asynchronous client
    specified (runner_async).
    """
    time.sleep(random.uniform(1, 2**attempts))


def get_metadata(path, refresh_token_if_needed=True):
    """
    Get the instance metadata at the provided path
    The path argument will be prepended by http://169.254.169.254/latest/
    If using IMDSv2 with tokens required, the token will be fetched and used for subsequent requests
    (unless refresh_token_if_needed is False, in which case this will fail if tokens are required
    and no token was already cached)
    """
    global __IMDS_Token__

    headers = {}
    if __IMDS_Token__ is not None:
        headers["X-aws-ec2-metadata-token"] = __IMDS_Token__

    # Connections to instance meta-data must fail fast and never be proxied
    result = requests.get(
        f"http://169.254.169.254/latest/{path}",
        proxies={"http": ""},
        headers=headers,
        timeout=AWS_METADATA_TIMEOUT,
    )

    if result.status_code == 401 and refresh_token_if_needed:
        # Probably using IMDSv2 with tokens required, so fetch token and retry
        token_result = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            proxies={"http": ""},
            timeout=AWS_METADATA_TIMEOUT,
        )
        __IMDS_Token__ = token_result.text
        if token_result.ok:
            return get_metadata(path, False)

    result.raise_for_status()
    return result


def creds(provider):
    """
    Return the credentials for AWS signing.  This could be just the id and key
    specified in the provider configuration, or if the id or key is set to the
    literal string 'use-instance-role-credentials' creds will pull the instance
    role credentials from the meta data, cache them, and provide them instead.
    """
    # Declare globals
    global __AccessKeyId__, __SecretAccessKey__, __Token__, __Expiration__

    ret_credentials = ()

    # if id or key is 'use-instance-role-credentials', pull them from meta-data
    ## if needed
    if provider["id"] == IROLE_CODE or provider["key"] == IROLE_CODE:
        # Check to see if we have cache credentials that are still good
        if not __Expiration__ or __Expiration__ < datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ):
            # We don't have any cached credentials, or they are expired, get them
            try:
                result = get_metadata("meta-data/iam/security-credentials/")
                role = result.text
            except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
                return provider["id"], provider["key"], ""

            try:
                result = get_metadata(f"meta-data/iam/security-credentials/{role}")
            except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
                return provider["id"], provider["key"], ""

            data = result.json()
            __AccessKeyId__ = data["AccessKeyId"]
            __SecretAccessKey__ = data["SecretAccessKey"]
            __Token__ = data["Token"]
            __Expiration__ = data["Expiration"]

        ret_credentials = __AccessKeyId__, __SecretAccessKey__, __Token__
    else:
        ret_credentials = provider["id"], provider["key"], ""

    if provider.get("role_arn") is not None:
        provider_shadow = provider.copy()
        provider_shadow.pop("role_arn", None)
        log.info("Assuming the role: %s", provider.get("role_arn"))
        ret_credentials = assumed_creds(
            provider_shadow, role_arn=provider.get("role_arn"), location="us-east-1"
        )

    return ret_credentials


def sig2(method, endpoint, params, provider, aws_api_version):
    """
    Sign a query against AWS services using Signature Version 2 Signing
    Process. This is documented at:

    http://docs.aws.amazon.com/general/latest/gr/signature-version-2.html
    """
    timenow = datetime.utcnow()
    timestamp = timenow.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Retrieve access credentials from meta-data, or use provided
    access_key_id, secret_access_key, token = creds(provider)

    params_with_headers = params.copy()
    params_with_headers["AWSAccessKeyId"] = access_key_id
    params_with_headers["SignatureVersion"] = "2"
    params_with_headers["SignatureMethod"] = "HmacSHA256"
    params_with_headers["Timestamp"] = f"{timestamp}"
    params_with_headers["Version"] = aws_api_version
    keys = sorted(params_with_headers.keys())
    values = list(list(map(params_with_headers.get, keys)))
    querystring = urllib.parse.urlencode(list(zip(keys, values)))

    canonical = "{}\n{}\n/\n{}".format(
        method.encode("utf-8"),
        endpoint.encode("utf-8"),
        querystring.encode("utf-8"),
    )

    hashed = hmac.new(secret_access_key, canonical, hashlib.sha256)
    sig = binascii.b2a_base64(hashed.digest())
    params_with_headers["Signature"] = sig.strip()

    # Add in security token if we have one
    if token != "":
        params_with_headers["SecurityToken"] = token

    return params_with_headers


def assumed_creds(prov_dict, role_arn, location=None):
    valid_session_name_re = re.compile("[^a-z0-9A-Z+=,.@-]")

    # current time in epoch seconds
    now = time.mktime(datetime.utcnow().timetuple())

    for key, creds in copy.deepcopy(__AssumeCache__).items():
        if (creds["Expiration"] - now) <= 120:
            del __AssumeCache__[key]

    if role_arn in __AssumeCache__:
        c = __AssumeCache__[role_arn]
        return c["AccessKeyId"], c["SecretAccessKey"], c["SessionToken"]

    version = "2011-06-15"
    session_name = valid_session_name_re.sub(
        "", salt.config.get_id({"root_dir": None})[0]
    )[0:63]

    headers, requesturl = sig4(
        "GET",
        "sts.amazonaws.com",
        params={
            "Version": version,
            "Action": "AssumeRole",
            "RoleSessionName": session_name,
            "RoleArn": role_arn,
            "Policy": (
                '{"Version":"2012-10-17","Statement":[{"Sid":"Stmt1",'
                ' "Effect":"Allow","Action":"*","Resource":"*"}]}'
            ),
            "DurationSeconds": "3600",
        },
        aws_api_version=version,
        data="",
        uri="/",
        prov_dict=prov_dict,
        product="sts",
        location=location,
        requesturl="https://sts.amazonaws.com/",
    )
    headers["Accept"] = "application/json"
    result = requests.request(
        "GET",
        requesturl,
        headers=headers,
        data="",
        verify=True,
        timeout=AWS_METADATA_TIMEOUT,
    )

    if result.status_code >= 400:
        log.info("AssumeRole response: %s", result.content)
    result.raise_for_status()
    resp = result.json()

    data = resp["AssumeRoleResponse"]["AssumeRoleResult"]["Credentials"]
    __AssumeCache__[role_arn] = data
    return data["AccessKeyId"], data["SecretAccessKey"], data["SessionToken"]


def sig4(
    method,
    endpoint,
    params,
    prov_dict,
    aws_api_version=DEFAULT_AWS_API_VERSION,
    location=None,
    product="ec2",
    uri="/",
    requesturl=None,
    data="",
    headers=None,
    role_arn=None,
    payload_hash=None,
):
    """
    Sign a query against AWS services using Signature Version 4 Signing
    Process. This is documented at:

    http://docs.aws.amazon.com/general/latest/gr/sigv4_signing.html
    http://docs.aws.amazon.com/general/latest/gr/sigv4-signed-request-examples.html
    http://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html
    """
    timenow = datetime.utcnow()

    # Retrieve access credentials from meta-data, or use provided
    if role_arn is None:
        access_key_id, secret_access_key, token = creds(prov_dict)
    else:
        access_key_id, secret_access_key, token = assumed_creds(
            prov_dict, role_arn, location=location
        )

    if location is None:
        location = get_region_from_metadata()
    if location is None:
        location = DEFAULT_LOCATION

    params_with_headers = params.copy()
    if product not in ("s3", "ssm"):
        params_with_headers["Version"] = aws_api_version
    keys = sorted(params_with_headers.keys())
    values = list(map(params_with_headers.get, keys))
    querystring = urllib.parse.urlencode(list(zip(keys, values))).replace("+", "%20")

    amzdate = timenow.strftime("%Y%m%dT%H%M%SZ")
    datestamp = timenow.strftime("%Y%m%d")
    new_headers = {}
    if isinstance(headers, dict):
        new_headers = headers.copy()

    # Create payload hash (hash of the request body content). For GET
    # requests, the payload is an empty string ('').
    if not payload_hash:
        payload_hash = salt.utils.hashutils.sha256_digest(data)

    new_headers["X-Amz-date"] = amzdate
    new_headers["host"] = endpoint
    new_headers["x-amz-content-sha256"] = payload_hash
    a_canonical_headers = []
    a_signed_headers = []

    if token != "":
        new_headers["X-Amz-security-token"] = token

    for header in sorted(new_headers.keys(), key=str.lower):
        lower_header = header.lower()
        a_canonical_headers.append(f"{lower_header}:{new_headers[header].strip()}")
        a_signed_headers.append(lower_header)
    canonical_headers = "\n".join(a_canonical_headers) + "\n"
    signed_headers = ";".join(a_signed_headers)

    algorithm = "AWS4-HMAC-SHA256"

    # Combine elements to create create canonical request
    canonical_request = "\n".join(
        (method, uri, querystring, canonical_headers, signed_headers, payload_hash)
    )

    # Create the string to sign
    credential_scope = "/".join((datestamp, location, product, "aws4_request"))
    string_to_sign = "\n".join(
        (
            algorithm,
            amzdate,
            credential_scope,
            salt.utils.hashutils.sha256_digest(canonical_request),
        )
    )

    # Create the signing key using the function defined above.
    signing_key = _sig_key(secret_access_key, datestamp, location, product)

    # Sign the string_to_sign using the signing_key
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Add signing information to the request
    authorization_header = "{} Credential={}/{}, SignedHeaders={}, Signature={}".format(
        algorithm,
        access_key_id,
        credential_scope,
        signed_headers,
        signature,
    )

    new_headers["Authorization"] = authorization_header

    requesturl = f"{requesturl}?{querystring}"
    return new_headers, requesturl


def _sign(key, msg):
    """
    Key derivation functions. See:

    http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
    """
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sig_key(key, date_stamp, regionName, serviceName):
    """
    Get a signature key. See:

    http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
    """
    kDate = _sign(("AWS4" + key).encode("utf-8"), date_stamp)
    if regionName:
        kRegion = _sign(kDate, regionName)
        kService = _sign(kRegion, serviceName)
    else:
        kService = _sign(kDate, serviceName)
    kSigning = _sign(kService, "aws4_request")
    return kSigning


def query(
    params=None,
    setname=None,
    requesturl=None,
    location=None,
    return_url=False,
    return_root=False,
    opts=None,
    provider=None,
    endpoint=None,
    product="ec2",
    sigver="2",
):
    """
    Perform a query against AWS services using Signature Version 2 Signing
    Process. This is documented at:

    http://docs.aws.amazon.com/general/latest/gr/signature-version-2.html

    Regions and endpoints are documented at:

    http://docs.aws.amazon.com/general/latest/gr/rande.html

    Default ``product`` is ``ec2``. Valid ``product`` names are:

    .. code-block:: yaml

        - autoscaling (Auto Scaling)
        - cloudformation (CloudFormation)
        - ec2 (Elastic Compute Cloud)
        - elasticache (ElastiCache)
        - elasticbeanstalk (Elastic BeanStalk)
        - elasticloadbalancing (Elastic Load Balancing)
        - elasticmapreduce (Elastic MapReduce)
        - iam (Identity and Access Management)
        - importexport (Import/Export)
        - monitoring (CloudWatch)
        - rds (Relational Database Service)
        - simpledb (SimpleDB)
        - sns (Simple Notification Service)
        - sqs (Simple Queue Service)
    """
    if params is None:
        params = {}

    if opts is None:
        opts = {}

    function = opts.get("function", (None, product))
    providers = opts.get("providers", {})

    if provider is None:
        prov_dict = providers.get(function[1], {}).get(product, {})
        if prov_dict:
            driver = list(list(prov_dict.keys()))[0]
            provider = providers.get(driver, product)
    else:
        prov_dict = providers.get(provider, {}).get(product, {})

    service_url = prov_dict.get("service_url", "amazonaws.com")

    if not location:
        location = get_location(opts, prov_dict)

    if endpoint is None:
        if not requesturl:
            endpoint = prov_dict.get("endpoint", f"{product}.{location}.{service_url}")

            requesturl = f"https://{endpoint}/"
        else:
            endpoint = urllib.parse.urlparse(requesturl).netloc
            if endpoint == "":
                endpoint_err = (
                    "Could not find a valid endpoint in the "
                    "requesturl: {}. Looking for something "
                    "like https://some.aws.endpoint/?args".format(requesturl)
                )
                log.error(endpoint_err)
                if return_url is True:
                    return {"error": endpoint_err}, requesturl
                return {"error": endpoint_err}

    log.debug("Using AWS endpoint: %s", endpoint)
    method = "GET"

    aws_api_version = prov_dict.get(
        "aws_api_version",
        prov_dict.get(f"{product}_api_version", DEFAULT_AWS_API_VERSION),
    )

    # Fallback to ec2's id & key if none is found, for this component
    if not prov_dict.get("id", None):
        prov_dict["id"] = providers.get(provider, {}).get("ec2", {}).get("id", {})
        prov_dict["key"] = providers.get(provider, {}).get("ec2", {}).get("key", {})

    if sigver == "4":
        headers, requesturl = sig4(
            method,
            endpoint,
            params,
            prov_dict,
            aws_api_version,
            location,
            product,
            requesturl=requesturl,
        )
        params_with_headers = {}
    else:
        params_with_headers = sig2(method, endpoint, params, prov_dict, aws_api_version)
        headers = {}

    attempts = 0
    while attempts < AWS_MAX_RETRIES:
        log.debug("AWS Request: %s", requesturl)
        log.trace("AWS Request Parameters: %s", params_with_headers)
        try:
            result = requests.get(
                requesturl,
                headers=headers,
                params=params_with_headers,
                timeout=AWS_METADATA_TIMEOUT,
            )
            log.debug("AWS Response Status Code: %s", result.status_code)
            log.trace("AWS Response Text: %s", result.text)
            result.raise_for_status()
            break
        except requests.exceptions.HTTPError as exc:
            root = ET.fromstring(exc.response.content)
            data = xml.to_dict(root)

            # check to see if we should retry the query
            err_code = data.get("Errors", {}).get("Error", {}).get("Code", "")
            if attempts < AWS_MAX_RETRIES and err_code and err_code in AWS_RETRY_CODES:
                attempts += 1
                log.error(
                    "AWS Response Status Code and Error: [%s %s] %s; "
                    "Attempts remaining: %s",
                    exc.response.status_code,
                    exc,
                    data,
                    attempts,
                )
                sleep_exponential_backoff(attempts)
                continue

            log.error(
                "AWS Response Status Code and Error: [%s %s] %s",
                exc.response.status_code,
                exc,
                data,
            )
            if return_url is True:
                return {"error": data}, requesturl
            return {"error": data}
    else:
        log.error(
            "AWS Response Status Code and Error: [%s %s] %s",
            exc.response.status_code,
            exc,
            data,
        )
        if return_url is True:
            return {"error": data}, requesturl
        return {"error": data}

    root = ET.fromstring(result.text)
    items = root[1]
    if return_root is True:
        items = root

    if setname:
        for idx, item in enumerate(root):
            comps = item.tag.split("}")
            if comps[1] == setname:
                items = root[idx]

    ret = []
    for item in items:
        ret.append(xml.to_dict(item))

    if return_url is True:
        return ret, requesturl

    return ret


def get_region_from_metadata():
    """
    Try to get region from instance identity document and cache it

    .. versionadded:: 2015.5.6
    """
    global __Location__

    if __Location__ == "do-not-get-from-metadata":
        log.debug(
            "Previously failed to get AWS region from metadata. Not trying again."
        )
        return None

    # Cached region
    if __Location__ != "":
        return __Location__

    try:
        result = get_metadata("dynamic/instance-identity/document")
    except requests.exceptions.RequestException:
        log.warning("Failed to get AWS region from instance metadata.", exc_info=True)
        # Do not try again
        __Location__ = "do-not-get-from-metadata"
        return None

    try:
        region = result.json()["region"]
        __Location__ = region
        return __Location__
    except (ValueError, KeyError):
        log.warning("Failed to decode JSON from instance metadata.")
        return None

    return None


def get_location(opts=None, provider=None):
    """
    Return the region to use, in this order:
        opts['location']
        provider['location']
        get_region_from_metadata()
        DEFAULT_LOCATION
    """
    if opts is None:
        opts = {}
    ret = opts.get("location")
    if ret is None and provider is not None:
        ret = provider.get("location")
    if ret is None:
        ret = get_region_from_metadata()
    if ret is None:
        ret = DEFAULT_LOCATION
    return ret

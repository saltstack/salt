"""
Connection library for Amazon S3

:depends: requests
"""

import logging
import urllib.parse
import xml.etree.ElementTree as ET

import salt.utils.aws
import salt.utils.files
import salt.utils.hashutils
import salt.utils.xmlutil as xml
from salt.exceptions import CommandExecutionError

try:
    import requests

    HAS_REQUESTS = True  # pylint: disable=W0612
except ImportError:
    HAS_REQUESTS = False  # pylint: disable=W0612


log = logging.getLogger(__name__)


def query(
    key,
    keyid,
    method="GET",
    params=None,
    headers=None,
    requesturl=None,
    return_url=False,
    bucket=None,
    service_url=None,
    path="",
    return_bin=False,
    action=None,
    local_file=None,
    verify_ssl=True,
    full_headers=False,
    kms_keyid=None,
    location=None,
    role_arn=None,
    chunk_size=16384,
    path_style=False,
    https_enable=True,
):
    """
    Perform a query against an S3-like API. This function requires that a
    secret key and the id for that key are passed in. For instance:

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    If keyid or key is not specified, an attempt to fetch them from EC2 IAM
    metadata service will be made.

    A service_url may also be specified in the configuration:

        s3.service_url: s3.amazonaws.com

    If a service_url is not specified, the default is s3.amazonaws.com. This
    may appear in various documentation as an "endpoint". A comprehensive list
    for Amazon S3 may be found at::

        http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region

    The service_url will form the basis for the final endpoint that is used to
    query the service.

    Path style can be enabled:

        s3.path_style: True

    This can be useful if you need to use salt with a proxy for an s3 compatible storage

    You can use either https protocol or http protocol:

        s3.https_enable: True

    SSL verification may also be turned off in the configuration:

        s3.verify_ssl: False

    This is required if using S3 bucket names that contain a period, as
    these will not match Amazon's S3 wildcard certificates. Certificate
    verification is enabled by default.

    A region may be specified:

        s3.location: eu-central-1

    If region is not specified, an attempt to fetch the region from EC2 IAM
    metadata service will be made. Failing that, default is us-east-1
    """
    if not HAS_REQUESTS:
        log.error("There was an error: requests is required for s3 access")

    if not headers:
        headers = {}

    if not params:
        params = {}

    if not service_url:
        service_url = "s3.amazonaws.com"

    if not bucket or path_style:
        endpoint = service_url
    else:
        endpoint = f"{bucket}.{service_url}"

    if path_style and bucket:
        path = f"{bucket}/{path}"

    # Try grabbing the credentials from the EC2 instance IAM metadata if available
    if not key:
        key = salt.utils.aws.IROLE_CODE

    if not keyid:
        keyid = salt.utils.aws.IROLE_CODE

    if kms_keyid is not None and method in ("PUT", "POST"):
        headers["x-amz-server-side-encryption"] = "aws:kms"
        headers["x-amz-server-side-encryption-aws-kms-key-id"] = kms_keyid

    if not location:
        location = salt.utils.aws.get_location()

    data = ""
    fh = None
    payload_hash = None
    if method == "PUT":
        if local_file:
            payload_hash = salt.utils.hashutils.get_hash(local_file, form="sha256")

    if path is None:
        path = ""
    path = urllib.parse.quote(path)

    if not requesturl:
        requesturl = "{}://{}/{}".format(
            "https" if https_enable else "http", endpoint, path
        )
        headers, requesturl = salt.utils.aws.sig4(
            method,
            endpoint,
            params,
            data=data,
            uri=f"/{path}",
            prov_dict={"id": keyid, "key": key},
            role_arn=role_arn,
            location=location,
            product="s3",
            requesturl=requesturl,
            headers=headers,
            payload_hash=payload_hash,
        )

    log.debug("S3 Request: %s", requesturl)
    log.debug("S3 Headers::")
    log.debug("    Authorization: %s", headers["Authorization"])

    if not data:
        data = None

    try:
        if method == "PUT":
            if local_file:
                # pylint: disable=resource-leakage
                fh = salt.utils.files.fopen(local_file, "rb")
                # pylint: enable=resource-leakage
                data = fh.read()  # pylint: disable=resource-leakage
            result = requests.request(
                method,
                requesturl,
                headers=headers,
                data=data,
                verify=verify_ssl,
                stream=True,
                timeout=300,
            )
        elif method == "GET" and local_file and not return_bin:
            result = requests.request(
                method,
                requesturl,
                headers=headers,
                data=data,
                verify=verify_ssl,
                stream=True,
                timeout=300,
            )
        else:
            result = requests.request(
                method,
                requesturl,
                headers=headers,
                data=data,
                verify=verify_ssl,
                timeout=300,
            )
    finally:
        if fh is not None:
            fh.close()

    err_code = None
    err_msg = None
    if result.status_code >= 400:
        # On error the S3 API response should contain error message
        err_text = result.content or "Unknown error"
        log.debug("    Response content: %s", err_text)

        # Try to get err info from response xml
        try:
            err_data = xml.to_dict(ET.fromstring(err_text))
            err_code = err_data["Code"]
            err_msg = err_data["Message"]
        except (KeyError, ET.ParseError) as err:
            log.debug(
                "Failed to parse s3 err response. %s: %s", type(err).__name__, err
            )
            err_code = f"http-{result.status_code}"
            err_msg = err_text

    log.debug("S3 Response Status Code: %s", result.status_code)

    if method == "PUT":
        if result.status_code != 200:
            if local_file:
                raise CommandExecutionError(
                    "Failed to upload from {} to {}. {}: {}".format(
                        local_file, path, err_code, err_msg
                    )
                )
            raise CommandExecutionError(
                f"Failed to create bucket {bucket}. {err_code}: {err_msg}"
            )

        if local_file:
            log.debug("Uploaded from %s to %s", local_file, path)
        else:
            log.debug("Created bucket %s", bucket)
        return

    if method == "DELETE":
        if not str(result.status_code).startswith("2"):
            if path:
                raise CommandExecutionError(
                    "Failed to delete {} from bucket {}. {}: {}".format(
                        path, bucket, err_code, err_msg
                    )
                )
            raise CommandExecutionError(
                f"Failed to delete bucket {bucket}. {err_code}: {err_msg}"
            )

        if path:
            log.debug("Deleted %s from bucket %s", path, bucket)
        else:
            log.debug("Deleted bucket %s", bucket)
        return

    # This can be used to save a binary object to disk
    if local_file and method == "GET":
        if result.status_code < 200 or result.status_code >= 300:
            raise CommandExecutionError(f"Failed to get file. {err_code}: {err_msg}")

        log.debug("Saving to local file: %s", local_file)
        with salt.utils.files.fopen(local_file, "wb") as out:
            for chunk in result.iter_content(chunk_size=chunk_size):
                out.write(chunk)
        return f"Saved to local file: {local_file}"

    if result.status_code < 200 or result.status_code >= 300:
        raise CommandExecutionError(f"Failed s3 operation. {err_code}: {err_msg}")

    # This can be used to return a binary object wholesale
    if return_bin:
        return result.content

    if result.content:
        items = ET.fromstring(result.content)

        ret = []
        for item in items:
            ret.append(xml.to_dict(item))

        if return_url is True:
            return ret, requesturl
    else:
        if result.status_code != requests.codes.ok:
            return
        ret = {"headers": []}
        if full_headers:
            ret["headers"] = dict(result.headers)
        else:
            for header in result.headers:
                ret["headers"].append(header.strip())

    return ret

"""
Functions to translate input in the docker CLI format to the format desired by
by the API.
"""

import os

import salt.utils.data
import salt.utils.network
from salt.exceptions import SaltInvocationError

NOTSET = object()


def split(item, sep=",", maxsplit=-1):
    return [x.strip() for x in item.split(sep, maxsplit)]


def get_port_def(port_num, proto="tcp"):
    """
    Given a port number and protocol, returns the port definition expected by
    docker-py. For TCP ports this is simply an integer, for UDP ports this is
    (port_num, 'udp').

    port_num can also be a string in the format 'port_num/udp'. If so, the
    "proto" argument will be ignored. The reason we need to be able to pass in
    the protocol separately is because this function is sometimes invoked on
    data derived from a port range (e.g. '2222-2223/udp'). In these cases the
    protocol has already been stripped off and the port range resolved into the
    start and end of the range, and get_port_def() is invoked once for each
    port number in that range. So, rather than munge udp ports back into
    strings before passing them to this function, the function will see if it
    has a string and use the protocol from it if present.

    This function does not catch the TypeError or ValueError which would be
    raised if the port number is non-numeric. This function either needs to be
    run on known good input, or should be run within a try/except that catches
    these two exceptions.
    """
    try:
        port_num, _, port_num_proto = port_num.partition("/")
    except AttributeError:
        pass
    else:
        if port_num_proto:
            proto = port_num_proto
    try:
        if proto.lower() == "udp":
            return int(port_num), "udp"
    except AttributeError:
        pass
    return int(port_num)


def get_port_range(port_def):
    """
    Given a port number or range, return a start and end to that range. Port
    ranges are defined as a string containing two numbers separated by a dash
    (e.g. '4505-4506').

    A ValueError will be raised if bad input is provided.
    """
    if isinstance(port_def, int):
        # Single integer, start/end of range is the same
        return port_def, port_def
    try:
        comps = [int(x) for x in split(port_def, "-")]
        if len(comps) == 1:
            range_start = range_end = comps[0]
        else:
            range_start, range_end = comps
        if range_start > range_end:
            raise ValueError("start > end")
    except (TypeError, ValueError) as exc:
        if str(exc) == "start > end":
            msg = (
                "Start of port range ({}) cannot be greater than end of "
                "port range ({})".format(range_start, range_end)
            )
        else:
            msg = f"'{port_def}' is non-numeric or an invalid port range"
        raise ValueError(msg)
    else:
        return range_start, range_end


def map_vals(val, *names, **extra_opts):
    """
    Many arguments come in as a list of VAL1:VAL2 pairs, but map to a list
    of dicts in the format {NAME1: VAL1, NAME2: VAL2}. This function
    provides common code to handle these instances.
    """
    fill = extra_opts.pop("fill", NOTSET)
    expected_num_elements = len(names)
    val = translate_stringlist(val)
    for idx, item in enumerate(val):
        if not isinstance(item, dict):
            elements = [x.strip() for x in item.split(":")]
            num_elements = len(elements)
            if num_elements < expected_num_elements:
                if fill is NOTSET:
                    raise SaltInvocationError(
                        "'{}' contains {} value(s) (expected {})".format(
                            item, num_elements, expected_num_elements
                        )
                    )
                elements.extend([fill] * (expected_num_elements - num_elements))
            elif num_elements > expected_num_elements:
                raise SaltInvocationError(
                    "'{}' contains {} value(s) (expected {})".format(
                        item,
                        num_elements,
                        (
                            expected_num_elements
                            if fill is NOTSET
                            else f"up to {expected_num_elements}"
                        ),
                    )
                )
            val[idx] = dict(zip(names, elements))
    return val


def validate_ip(val):
    try:
        if not salt.utils.network.is_ip(val):
            raise SaltInvocationError(f"'{val}' is not a valid IP address")
    except RuntimeError:
        pass


def validate_subnet(val):
    try:
        if not salt.utils.network.is_subnet(val):
            raise SaltInvocationError(f"'{val}' is not a valid subnet")
    except RuntimeError:
        pass


def translate_str(val):
    return str(val) if not isinstance(val, str) else val


def translate_int(val):
    if not isinstance(val, int):
        try:
            val = int(val)
        except (TypeError, ValueError):
            raise SaltInvocationError(f"'{val}' is not an integer")
    return val


def translate_bool(val):
    return bool(val) if not isinstance(val, bool) else val


def translate_dict(val):
    """
    Not really translating, just raising an exception if it's not a dict
    """
    if not isinstance(val, dict):
        raise SaltInvocationError(f"'{val}' is not a dictionary")
    return val


def translate_command(val):
    """
    Input should either be a single string, or a list of strings. This is used
    for the two args that deal with commands ("command" and "entrypoint").
    """
    if isinstance(val, str):
        return val
    elif isinstance(val, list):
        for idx, item in enumerate(val):
            if not isinstance(item, str):
                val[idx] = str(item)
    else:
        # Make sure we have a string
        val = str(val)
    return val


def translate_bytes(val):
    """
    These values can be expressed as an integer number of bytes, or a string
    expression (i.e. 100mb, 1gb, etc.).
    """
    try:
        val = int(val)
    except (TypeError, ValueError):
        if not isinstance(val, str):
            val = str(val)
    return val


def translate_stringlist(val):
    """
    On the CLI, these are passed as multiple instances of a given CLI option.
    In Salt, we accept these as a comma-delimited list but the API expects a
    Python list. This function accepts input and returns it back as a Python
    list of strings. If the input is a string which is a comma-separated list
    of items, split that string and return it.
    """
    if not isinstance(val, list):
        try:
            val = split(val)
        except AttributeError:
            val = split(str(val))
    for idx, item in enumerate(val):
        if not isinstance(item, str):
            val[idx] = str(item)
    return val


def translate_device_rates(val, numeric_rate=True):
    """
    CLI input is a list of PATH:RATE pairs, but the API expects a list of
    dictionaries in the format [{'Path': path, 'Rate': rate}]
    """
    val = map_vals(val, "Path", "Rate")
    for item in val:
        try:
            is_abs = os.path.isabs(item["Path"])
        except AttributeError:
            is_abs = False
        if not is_abs:
            raise SaltInvocationError("Path '{Path}' is not absolute".format(**item))

        # Attempt to convert to an integer. Will fail if rate was specified as
        # a shorthand (e.g. 1mb), this is OK as we will check to make sure the
        # value is an integer below if that is what is required.
        try:
            item["Rate"] = int(item["Rate"])
        except (TypeError, ValueError):
            pass

        if numeric_rate:
            try:
                item["Rate"] = int(item["Rate"])
            except ValueError:
                raise SaltInvocationError(
                    "Rate '{Rate}' for path '{Path}' is non-numeric".format(**item)
                )
    return val


def translate_key_val(val, delimiter="="):
    """
    CLI input is a list of key/val pairs, but the API expects a dictionary in
    the format {key: val}
    """
    if isinstance(val, dict):
        return val
    val = translate_stringlist(val)
    new_val = {}
    for item in val:
        try:
            lvalue, rvalue = split(item, delimiter, 1)
        except (AttributeError, TypeError, ValueError):
            raise SaltInvocationError(f"'{item}' is not a key{delimiter}value pair")
        new_val[lvalue] = rvalue
    return new_val


def translate_labels(val):
    """
    Can either be a list of label names, or a list of name=value pairs. The API
    can accept either a list of label names or a dictionary mapping names to
    values, so the value we translate will be different depending on the input.
    """
    if not isinstance(val, dict):
        if not isinstance(val, list):
            val = split(val)
        new_val = {}
        for item in val:
            if isinstance(item, dict):
                if len(item) != 1:
                    raise SaltInvocationError("Invalid label(s)")
                key = next(iter(item))
                val = item[key]
            else:
                try:
                    key, val = split(item, "=", 1)
                except ValueError:
                    key = item
                    val = ""
            if not isinstance(key, str):
                key = str(key)
            if not isinstance(val, str):
                val = str(val)
            new_val[key] = val
        val = new_val
    return val

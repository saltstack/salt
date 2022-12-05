from copy import deepcopy

from salt.utils import object_filter

REDACTED = "REDACTED"
REDACTED_BYTES = bytes(REDACTED, "utf-8")

REDACTED_DATA = ("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN PGP PRIVATE KEY-----")
REDACTED_DATA_BYTES = tuple(bytes(data, "utf-8") for data in REDACTED_DATA)


def _redact_check(address_list, redacted_data, redacted_data_bytes):
    for data_point, _, _ in address_list:
        if isinstance(data_point, str):
            for r in redacted_data:
                if r in data_point:
                    return True
        elif isinstance(data_point, bytes):
            for r in redacted_data_bytes:
                if r in data_point:
                    return True
        else:
            return True
    return False


def _redact_write(value, data, address):
    if object_filter.write_check(address):
        return object_filter.write(value, data, address)
    value = REDACTED
    sub_address = address[:-1]
    while sub_address:
        if object_filter.write_check(sub_address):
            return object_filter.write(value, data, sub_address)
        sub_address = sub_address[:-1]


def _redact(data, address_list, redacted_data, redacted_data_bytes):
    for data_point, address, _ in address_list:
        if isinstance(data_point, str):
            for r in redacted_data:
                if r in data_point:
                    data = _redact_write(REDACTED, data, address)
                    break
        elif isinstance(data_point, bytes):
            for r in redacted_data_bytes:
                if r in data_point:
                    data = _redact_write(REDACTED_BYTES, data, address)
                    break
        else:
            data = _redact_write(str(data_point), data, address)
    return data


def redact(data, redacted_data=None):
    """
    Find sensitive data in nested structures and redact it.
    """
    if redacted_data is None:
        redacted_data = REDACTED_DATA
        redacted_data_bytes = REDACTED_DATA_BYTES
    else:
        redacted_data_bytes = tuple(bytes(data, "utf-8") for data in redacted_data)
    try:
        working_data = data
        address_list = object_filter.object_filter(data, (str, bytes), True, True)
        while _redact_check(address_list, redacted_data, redacted_data_bytes):
            if working_data is data:
                working_data = deepcopy(data)
            working_data = _redact(
                working_data, address_list, redacted_data, redacted_data_bytes
            )
            address_list = object_filter.object_filter(
                working_data, (str, bytes), True, True
            )
        return working_data
    except (RecursionError, TypeError) as e:
        return f"{REDACTED}-{type(e).__name__}"

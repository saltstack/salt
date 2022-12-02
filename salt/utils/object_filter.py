from collections import namedtuple

NONE = type(None)

AddressPoint = namedtuple("AddressPoint", ("point", "key", "mutable"))


def write_check(address):
    """ """
    for spot, point in enumerate(address):
        if not point.mutable:
            return False
        if spot + 1 != len(address) and point.key:
            return False
    return True


def write(value, data, address):
    """ """
    if len(address) == 0:
        return value
    assert write_check(address)
    data_child = data
    for point in address[:-1]:
        data_child = data_child[point.point]
    point = address[-1]
    if isinstance(data_child, set):
        data_child.remove(point.point)
        data_child.add(value)
    elif point.key:
        key_item = data_child[point.point]
        del data_child[point.point]
        data_child[value] = key_item
    elif isinstance(data_child, (dict, list)):
        data_child[point.point] = value
    else:
        vars(data_child)[point.point] = value
    return data


def object_filter(data, types=None, keys=True, unsupported=True):
    """ """
    address_list = []
    _object_filter(data, types, keys, unsupported, (), address_list)
    return address_list


def _object_filter(data, types, keys, unsupported, address, address_list):
    supported = True
    if isinstance(data, tuple):
        for spot, d in enumerate(data):
            _object_filter(
                d,
                types,
                keys,
                unsupported,
                (*address, AddressPoint(spot, False, False)),
                address_list,
            )
    elif isinstance(data, (list, bytearray)):
        for spot, d in enumerate(data):
            _object_filter(
                d,
                types,
                keys,
                unsupported,
                (*address, AddressPoint(spot, False, True)),
                address_list,
            )
    elif isinstance(data, frozenset):
        for d in data:
            _object_filter(
                d,
                types,
                keys,
                unsupported,
                (*address, AddressPoint(d, True, False)),
                address_list,
            )
    elif isinstance(data, set):
        for d in data:
            _object_filter(
                d,
                types,
                keys,
                unsupported,
                (*address, AddressPoint(d, True, True)),
                address_list,
            )
    elif isinstance(data, dict):
        for k, d in data.items():
            _object_filter(
                d,
                types,
                keys,
                unsupported,
                (*address, AddressPoint(k, False, True)),
                address_list,
            )
            if keys:
                _object_filter(
                    k,
                    types,
                    keys,
                    unsupported,
                    (*address, AddressPoint(k, True, True)),
                    address_list,
                )
    elif not isinstance(data, (NONE, int, float, complex, str, bytes, bool)):
        try:
            for k, d in vars(data).items():
                _object_filter(
                    d,
                    types,
                    keys,
                    unsupported,
                    (*address, AddressPoint(k, False, True)),
                    address_list,
                )
                if keys:
                    _object_filter(
                        k,
                        types,
                        keys,
                        unsupported,
                        (*address, AddressPoint(k, True, True)),
                        address_list,
                    )
        except TypeError:
            supported = False

    if types is None:
        if unsupported or supported:
            address_list.append((data, address, supported))
    elif isinstance(data, types) or (not supported and unsupported):
        address_list.append((data, address, supported))

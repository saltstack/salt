# -*- coding: utf-8 -*-
'''
Functions to translate input in the docker CLI format to the format desired by
by the API.
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt libs
import salt.utils.network
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range, zip  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)
NOTSET = object()


def _split(item, sep=',', maxsplit=-1):
    return [x.strip() for x in item.split(sep, maxsplit)]


def _get_port_def(port_num, proto='tcp'):
    '''
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
    '''
    try:
        port_num, _, port_num_proto = port_num.partition('/')
    except AttributeError:
        pass
    else:
        if port_num_proto:
            proto = port_num_proto
    try:
        if proto.lower() == 'udp':
            return int(port_num), 'udp'
    except AttributeError:
        pass
    return int(port_num)


def _get_port_range(port_def):
    '''
    Given a port number or range, return a start and end to that range. Port
    ranges are defined as a string containing two numbers separated by a dash
    (e.g. '4505-4506').

    A ValueError will be raised if bad input is provided.
    '''
    if isinstance(port_def, six.integer_types):
        # Single integer, start/end of range is the same
        return port_def, port_def
    try:
        comps = [int(x) for x in _split(port_def, '-')]
        if len(comps) == 1:
            range_start = range_end = comps[0]
        else:
            range_start, range_end = comps
        if range_start > range_end:
            raise ValueError('start > end')
    except (TypeError, ValueError) as exc:
        if exc.__str__() == 'start > end':
            msg = (
                'Start of port range ({0}) cannot be greater than end of '
                'port range ({1})'.format(range_start, range_end)
            )
        else:
            msg = '\'{0}\' is non-numeric or an invalid port range'.format(
                port_def
            )
        raise ValueError(msg)
    else:
        return range_start, range_end


def _map_vals(val, *names, **extra_opts):
    '''
    Many arguments come in as a list of VAL1:VAL2 pairs, but map to a list
    of dicts in the format {NAME1: VAL1, NAME2: VAL2}. This function
    provides common code to handle these instances.
    '''
    fill = extra_opts.pop('fill', NOTSET)
    expected_num_elements = len(names)
    val = _translate_stringlist(val)
    for idx, item in enumerate(val):
        if not isinstance(item, dict):
            elements = [x.strip() for x in item.split(':')]
            num_elements = len(elements)
            if num_elements < expected_num_elements:
                if fill is NOTSET:
                    raise SaltInvocationError(
                        '\'{0}\' contains {1} value(s) (expected {2})'.format(
                            item, num_elements, expected_num_elements
                        )
                    )
                elements.extend([fill] * (expected_num_elements - num_elements))
            elif num_elements > expected_num_elements:
                raise SaltInvocationError(
                    '\'{0}\' contains {1} value(s) (expected {2})'.format(
                        item,
                        num_elements,
                        expected_num_elements if fill is NOTSET
                            else 'up to {0}'.format(expected_num_elements)
                    )
                )
            val[idx] = dict(zip(names, elements))
    return val


def _validate_ip(val):
    try:
        if not salt.utils.network.is_ip(val):
            raise SaltInvocationError(
                '\'{0}\' is not a valid IP address'.format(val)
            )
    except RuntimeError:
        pass


# Helpers to perform common translation actions
def _translate_str(val):
    return str(val) if not isinstance(val, six.string_types) else val


def _translate_int(val):
    if not isinstance(val, six.integer_types):
        try:
            val = int(val)
        except (TypeError, ValueError):
            raise SaltInvocationError('\'{0}\' is not an integer'.format(val))
    return val


def _translate_bool(val):
    return bool(val) if not isinstance(val, bool) else val


def _translate_dict(val):
    '''
    Not really translating, just raising an exception if it's not a dict
    '''
    if not isinstance(val, dict):
        raise SaltInvocationError('\'{0}\' is not a dictionary'.format(val))
    return val


def _translate_command(val):
    '''
    Input should either be a single string, or a list of strings. This is used
    for the two args that deal with commands ("command" and "entrypoint").
    '''
    if isinstance(val, six.string_types):
        return val
    elif isinstance(val, list):
        for idx in range(len(val)):
            if not isinstance(val[idx], six.string_types):
                val[idx] = str(val[idx])
    else:
        # Make sure we have a string
        val = str(val)
    return val


def _translate_bytes(val):
    '''
    These values can be expressed as an integer number of bytes, or a string
    expression (i.e. 100mb, 1gb, etc.).
    '''
    try:
        val = int(val)
    except (TypeError, ValueError):
        if not isinstance(val, six.string_types):
            val = str(val)
    return val


def _translate_stringlist(val):
    '''
    On the CLI, these are passed as multiple instances of a given CLI option.
    In Salt, we accept these as a comma-delimited list but the API expects a
    Python list. This function accepts input and returns it back as a Python
    list of strings. If the input is a string which is a comma-separated list
    of items, split that string and return it.
    '''
    if not isinstance(val, list):
        try:
            val = _split(val)
        except AttributeError:
            val = _split(str(val))
    for idx in range(len(val)):
        if not isinstance(val[idx], six.string_types):
            val[idx] = str(val[idx])
    return val


def _translate_device_rates(val, numeric_rate=True):
    '''
    CLI input is a list of PATH:RATE pairs, but the API expects a list of
    dictionaries in the format [{'Path': path, 'Rate': rate}]
    '''
    val = _map_vals(val, 'Path', 'Rate')
    for idx in range(len(val)):
        try:
            is_abs = os.path.isabs(val[idx]['Path'])
        except AttributeError:
            is_abs = False
        if not is_abs:
            raise SaltInvocationError(
                'Path \'{Path}\' is not absolute'.format(**val[idx])
            )

        # Attempt to convert to an integer. Will fail if rate was specified as
        # a shorthand (e.g. 1mb), this is OK as we will check to make sure the
        # value is an integer below if that is what is required.
        try:
            val[idx]['Rate'] = int(val[idx]['Rate'])
        except (TypeError, ValueError):
            pass

        if numeric_rate:
            try:
                val[idx]['Rate'] = int(val[idx]['Rate'])
            except ValueError:
                raise SaltInvocationError(
                    'Rate \'{Rate}\' for path \'{Path}\' is '
                    'non-numeric'.format(**val[idx])
                )
    return val


def _translate_key_val(val, delimiter='='):
    '''
    CLI input is a list of key/val pairs, but the API expects a dictionary in
    the format {key: val}
    '''
    if isinstance(val, dict):
        return val
    val = _translate_stringlist(val)
    new_val = {}
    for item in val:
        try:
            lvalue, rvalue = _split(item, delimiter, 1)
        except (AttributeError, TypeError, ValueError):
            raise SaltInvocationError(
                '\'{0}\' is not a key{1}value pair'.format(item, delimiter)
            )
        new_val[lvalue] = rvalue
    return new_val


# Functions below must match names of API arguments
def auto_remove(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def binds(val, **kwargs):  # pylint: disable=unused-argument
    '''
    On the CLI, these are passed as multiple instances of a given CLI option.
    In Salt, we accept these as a comma-delimited list but the API expects a
    Python list.
    '''
    if not isinstance(val, dict):
        if not isinstance(val, list):
            try:
                val = _split(val)
            except AttributeError:
                raise SaltInvocationError(
                    '\'{0}\' is not a dictionary or list of bind '
                    'definitions'.format(val)
                )
    return val


def blkio_weight(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def blkio_weight_device(val, **kwargs):  # pylint: disable=unused-argument
    '''
    CLI input is a list of PATH:WEIGHT pairs, but the API expects a list of
    dictionaries in the format [{'Path': path, 'Weight': weight}]
    '''
    val = _map_vals(val, 'Path', 'Weight')
    for idx in range(len(val)):
        try:
            val[idx]['Weight'] = int(val[idx]['Weight'])
        except (TypeError, ValueError):
            raise SaltInvocationError(
                'Weight \'{Weight}\' for path \'{Path}\' is not an '
                'integer'.format(**val[idx])
            )
    return val


def cap_add(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def cap_drop(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def command(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_command(val)


def cpuset_cpus(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def cpuset_mems(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def cpu_group(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def cpu_period(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def cpu_shares(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def detach(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def device_read_bps(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_device_rates(val, numeric_rate=False)


def device_read_iops(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_device_rates(val, numeric_rate=True)


def device_write_bps(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_device_rates(val, numeric_rate=False)


def device_write_iops(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_device_rates(val, numeric_rate=True)


def devices(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def dns_opt(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def dns_search(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def dns(val, **kwargs):
    val = _translate_stringlist(val)
    if kwargs.get('validate_ip_addrs', True):
        for item in val:
            _validate_ip(item)
    return val


def domainname(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def entrypoint(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_command(val)


def environment(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_key_val(val, delimiter='=')


def extra_hosts(val, **kwargs):
    val = _translate_key_val(val, delimiter=':')
    if kwargs.get('validate_ip_addrs', True):
        for key in val:
            _validate_ip(val[key])
    return val


def group_add(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def host_config(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_dict(val)


def hostname(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def ipc_mode(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def isolation(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def labels(val, **kwargs):  # pylint: disable=unused-argument
    '''
    Can either be a list of label names, or a list of name=value pairs. The API
    can accept either a list of label names or a dictionary mapping names to
    values, so the value we translate will be different depending on the input.
    '''
    if not isinstance(val, dict):
        val = _translate_stringlist(val)
        try:
            has_mappings = all('=' in x for x in val)
        except TypeError:
            has_mappings = False

        if has_mappings:
            # The try/except above where has_mappings was defined has
            # already confirmed that all elements are strings, and that
            # all contain an equal sign. So we do not need to enclose
            # the split in another try/except.
            val = dict([_split(x, '=', 1) for x in val])
        else:
            # Stringify any non-string values
            for idx in range(len(val)):
                if '=' in val[idx]:
                    raise SaltInvocationError(
                        'Mix of labels with and without values'
                    )
            return val
    return val


def links(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_key_val(val, delimiter=':')


def log_driver(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def log_opt(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_key_val(val, delimiter='=')


def lxc_conf(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_key_val(val, delimiter='=')


def mac_address(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def mem_limit(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bytes(val)


def mem_swappiness(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def memswap_limit(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bytes(val)


def name(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def network_disabled(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def network_mode(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def oom_kill_disable(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def oom_score_adj(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def pid_mode(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def pids_limit(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def port_bindings(val, **kwargs):
    '''
    On the CLI, these are passed as multiple instances of a given CLI option.
    In Salt, we accept these as a comma-delimited list but the API expects a
    Python dictionary mapping ports to their bindings. The format the API
    expects is complicated depending on whether or not the external port maps
    to a different internal port, or if the port binding is for UDP instead of
    TCP (the default). For reference, see the "Port bindings" section in the
    docker-py documentation at the following URL:
    http://docker-py.readthedocs.io/en/stable/api.html
    '''
    validate_ip_addrs = kwargs.get('validate_ip_addrs', True)
    if not isinstance(val, dict):
        if not isinstance(val, list):
            try:
                val = _split(val)
            except AttributeError:
                val = _split(str(val))

        for idx in range(len(val)):
            if not isinstance(val[idx], six.string_types):
                val[idx] = str(val[idx])

        def _format_port(port_num, proto):
            return str(port_num) + '/udp' if proto.lower() == 'udp' else port_num

        bindings = {}
        for binding in val:
            bind_parts = _split(binding, ':')
            num_bind_parts = len(bind_parts)
            if num_bind_parts == 1:
                # Single port or port range being passed through (no
                # special mapping)
                container_port = str(bind_parts[0])
                if container_port == '':
                    raise SaltInvocationError(
                        'Empty port binding definition found'
                    )
                container_port, _, proto = container_port.partition('/')
                try:
                    start, end = _get_port_range(container_port)
                except ValueError as exc:
                    # Using __str__() to avoid deprecation warning for using
                    # the message attribute of the ValueError.
                    raise SaltInvocationError(exc.__str__())
                bind_vals = [
                    (_format_port(port_num, proto), None)
                    for port_num in range(start, end + 1)
                ]
            elif num_bind_parts == 2:
                if bind_parts[0] == '':
                    raise SaltInvocationError(
                        'Empty host port in port binding definition '
                        '\'{0}\''.format(binding)
                    )
                if bind_parts[1] == '':
                    raise SaltInvocationError(
                        'Empty container port in port binding definition '
                        '\'{0}\''.format(binding)
                    )
                container_port, _, proto = bind_parts[1].partition('/')
                try:
                    cport_start, cport_end = _get_port_range(container_port)
                    hport_start, hport_end = _get_port_range(bind_parts[0])
                except ValueError as exc:
                    # Using __str__() to avoid deprecation warning for
                    # using the message attribute of the ValueError.
                    raise SaltInvocationError(exc.__str__())
                if (hport_end - hport_start) != (cport_end - cport_start):
                    # Port range is mismatched
                    raise SaltInvocationError(
                        'Host port range ({0}) does not have the same '
                        'number of ports as the container port range '
                        '({1})'.format(bind_parts[0], container_port)
                    )
                cport_list = list(range(cport_start, cport_end + 1))
                hport_list = list(range(hport_start, hport_end + 1))
                bind_vals = [
                    (_format_port(cport_list[x], proto), hport_list[x])
                    for x in range(len(cport_list))
                ]
            elif num_bind_parts == 3:
                host_ip, host_port = bind_parts[0:2]
                if validate_ip_addrs:
                    _validate_ip(host_ip)
                container_port, _, proto = bind_parts[2].partition('/')
                try:
                    cport_start, cport_end = _get_port_range(container_port)
                except ValueError as exc:
                    # Using __str__() to avoid deprecation warning for
                    # using the message attribute of the ValueError.
                    raise SaltInvocationError(exc.__str__())
                cport_list = list(range(cport_start, cport_end + 1))
                if host_port == '':
                    hport_list = [None] * len(cport_list)
                else:
                    try:
                        hport_start, hport_end = _get_port_range(host_port)
                    except ValueError as exc:
                        # Using __str__() to avoid deprecation warning for
                        # using the message attribute of the ValueError.
                        raise SaltInvocationError(exc.__str__())
                    hport_list = list(range(hport_start, hport_end + 1))

                    if (hport_end - hport_start) != (cport_end - cport_start):
                        # Port range is mismatched
                        raise SaltInvocationError(
                            'Host port range ({0}) does not have the same '
                            'number of ports as the container port range '
                            '({1})'.format(host_port, container_port)
                        )

                bind_vals = [(
                    _format_port(val, proto),
                    (host_ip,) if hport_list[idx] is None
                        else (host_ip, hport_list[idx])
                ) for idx, val in enumerate(cport_list)]
            else:
                raise SaltInvocationError(
                    '\'{0}\' is an invalid port binding definition (at most '
                    '3 components are allowed, found {1})'.format(
                        binding, num_bind_parts
                    )
                )

            for cport, bind_def in bind_vals:
                if cport not in bindings:
                    bindings[cport] = bind_def
                else:
                    if isinstance(bindings[cport], list):
                        # Append to existing list of bindings for this
                        # container port.
                        bindings[cport].append(bind_def)
                    else:
                        bindings[cport] = [bindings[cport], bind_def]
                    for idx in range(len(bindings[cport])):
                        if bindings[cport][idx] is None:
                            # Now that we are adding multiple
                            # bindings
                            try:
                                # Convert 1234/udp to 1234
                                bindings[cport][idx] = int(cport.split('/')[0])
                            except AttributeError:
                                # Port was tcp, the AttributeError
                                # signifies that the split failed
                                # because the port number was
                                # already defined as an integer.
                                # Just use the cport.
                                bindings[cport][idx] = cport
        val = bindings
    return val


def ports(val, **kwargs):  # pylint: disable=unused-argument
    '''
    Like cap_add, cap_drop, etc., this option can be specified multiple times,
    and each time can be a port number or port range. Ultimately, the API
    expects a list, but elements in the list are ints when the port is TCP, and
    a tuple (port_num, 'udp') when the port is UDP.
    '''
    if not isinstance(val, list):
        try:
            val = _split(val)
        except AttributeError:
            if isinstance(val, six.integer_types):
                val = [val]
            else:
                raise SaltInvocationError(
                    '\'{0}\' is not a valid port definition'.format(val)
                )
    new_ports = set()
    for item in val:
        if isinstance(item, six.integer_types):
            new_ports.add(item)
            continue
        try:
            item, _, proto = item.partition('/')
        except AttributeError:
            raise SaltInvocationError(
                '\'{0}\' is not a valid port definition'.format(item)
            )
        try:
            range_start, range_end = _get_port_range(item)
        except ValueError as exc:
            # Using __str__() to avoid deprecation warning for using
            # the "message" attribute of the ValueError.
            raise SaltInvocationError(exc.__str__())
        new_ports.update([_get_port_def(x, proto)
                          for x in range(range_start, range_end + 1)])
    return sorted(new_ports)


def privileged(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def publish_all_ports(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def read_only(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def restart_policy(val, **kwargs):  # pylint: disable=unused-argument
    '''
    CLI input is in the format NAME[:RETRY_COUNT] but the API expects {'Name':
    name, 'MaximumRetryCount': retry_count}. We will use the 'fill' kwarg here
    to make sure the mapped result uses '0' for the count if this optional
    value was omitted.
    '''
    val = _map_vals(val, 'Name', 'MaximumRetryCount', fill='0')
    # _map_vals() converts the input into a list of dicts, but the API
    # wants just a dict, so extract the value from the single-element
    # list. If there was more than one element in the list, then
    # invalid input was passed (i.e. a comma-separated list, when what
    # we wanted was a single value).
    if len(val) != 1:
        raise SaltInvocationError('Only one policy is permitted')
    val = val[0]
    try:
        # The count needs to be an integer
        val['MaximumRetryCount'] = int(val['MaximumRetryCount'])
    except (TypeError, ValueError):
        # Non-numeric retry count passed
        raise SaltInvocationError(
            'Retry count \'{0}\' is non-numeric'.format(val['MaximumRetryCount'])
        )
    return val


def security_opt(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def shm_size(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bytes(val)


def stdin_open(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def stop_signal(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def stop_timeout(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_int(val)


def storage_opt(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_key_val(val, delimiter='=')


def sysctls(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_key_val(val, delimiter='=')


def tmpfs(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_dict(val)


def tty(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_bool(val)


def ulimits(val, **kwargs):  # pylint: disable=unused-argument
    val = _translate_stringlist(val)
    for idx in range(len(val)):
        if not isinstance(val[idx], dict):
            try:
                ulimit_name, limits = _split(val[idx], '=', 1)
                comps = _split(limits, ':', 1)
            except (AttributeError, ValueError):
                raise SaltInvocationError(
                    'Ulimit definition \'{0}\' is not in the format '
                    'type=soft_limit[:hard_limit]'.format(val[idx])
                )
            if len(comps) == 1:
                comps *= 2
            soft_limit, hard_limit = comps
            try:
                val[idx] = {'Name': ulimit_name,
                            'Soft': int(soft_limit),
                            'Hard': int(hard_limit)}
            except (TypeError, ValueError):
                raise SaltInvocationError(
                    'Limit \'{0}\' contains non-numeric value(s)'.format(
                        val[idx]
                    )
                )
    return val


def user(val, **kwargs):  # pylint: disable=unused-argument
    '''
    This can be either a string or a numeric uid
    '''
    if not isinstance(val, six.integer_types):
        # Try to convert to integer. This will fail if the value is a
        # username. This is OK, as we check below to make sure that the
        # value is either a string or integer. Trying to convert to an
        # integer first though will allow us to catch the edge case in
        # which a quoted uid is passed (e.g. '1000').
        try:
            val = int(val)
        except (TypeError, ValueError):
            pass
    if not isinstance(val, (six.integer_types, six.string_types)):
        raise SaltInvocationError('Value must be a username or uid')
    elif isinstance(val, six.integer_types) and val < 0:
        raise SaltInvocationError('\'{0}\' is an invalid uid'.format(val))
    return val


def userns_mode(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def volume_driver(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_str(val)


def volumes(val, **kwargs):  # pylint: disable=unused-argument
    '''
    Should be a list of absolute paths
    '''
    val = _translate_stringlist(val)
    for item in val:
        if not os.path.isabs(item):
            raise SaltInvocationError(
                '\'{0}\' is not an absolute path'.format(item)
            )
    return val


def volumes_from(val, **kwargs):  # pylint: disable=unused-argument
    return _translate_stringlist(val)


def working_dir(val, **kwargs):  # pylint: disable=unused-argument
    '''
    Must be an absolute path
    '''
    try:
        is_abs = os.path.isabs(val)
    except AttributeError:
        is_abs = False
    if not is_abs:
        raise SaltInvocationError('\'{0}\' is not an absolute path'.format(val))
    return val

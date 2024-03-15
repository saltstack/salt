import datetime
import re
import string

from salt.exceptions import InvalidConfigError, SaltInvocationError

SALT_RUNTYPE_MASTER = 0
SALT_RUNTYPE_MASTER_IMPERSONATING = 1
SALT_RUNTYPE_MASTER_PEER_RUN = 2
SALT_RUNTYPE_MINION_LOCAL = 3
SALT_RUNTYPE_MINION_REMOTE = 4


def _get_salt_run_type(opts):
    if "vault" in opts and opts.get("__role", "minion") == "master":
        if opts.get("minion_id"):
            return SALT_RUNTYPE_MASTER_IMPERSONATING
        if "grains" in opts and "id" in opts["grains"]:
            return SALT_RUNTYPE_MASTER_PEER_RUN
        return SALT_RUNTYPE_MASTER

    config_location = opts.get("vault", {}).get("config_location")
    if config_location and config_location not in ["local", "master"]:
        raise InvalidConfigError(
            "Invalid vault configuration: config_location must be either local or master"
        )

    if config_location == "master":
        pass
    elif any(
        (
            opts.get("local", None),
            opts.get("file_client", None) == "local",
            opts.get("master_type", None) == "disable",
            config_location == "local",
        )
    ):
        return SALT_RUNTYPE_MINION_LOCAL
    return SALT_RUNTYPE_MINION_REMOTE


def iso_to_timestamp(iso_time):
    """
    Most endpoints respond with RFC3339-formatted strings
    This is a hacky way to use inbuilt tools only for converting
    to a timestamp
    """
    # drop subsecond precision to make it easier on us
    # (length would need to be 3, 6 or 9)
    iso_time = re.sub(r"\.[\d]+", "", iso_time)
    iso_time = re.sub(r"Z$", "+00:00", iso_time)
    try:
        # Python >=v3.7
        return int(datetime.datetime.fromisoformat(iso_time).timestamp())
    except AttributeError:
        # Python < v3.7
        dstr, tstr = iso_time.split("T")
        year = int(dstr[:4])
        month = int(dstr[5:7])
        day = int(dstr[8:10])
        hour = int(tstr[:2])
        minute = int(tstr[3:5])
        second = int(tstr[6:8])
        tz_pos = (tstr.find("-") + 1 or tstr.find("+") + 1) - 1
        tz_hour = int(tstr[tz_pos + 1 : tz_pos + 3])
        tz_minute = int(tstr[tz_pos + 4 : tz_pos + 6])
        if all(x == 0 for x in (tz_hour, tz_minute)):
            tz = datetime.timezone.utc
        else:
            tz_sign = -1 if tstr[tz_pos] == "-" else 1
            td = datetime.timedelta(hours=tz_hour, minutes=tz_minute)
            tz = datetime.timezone(tz_sign * td)
        return int(
            datetime.datetime(year, month, day, hour, minute, second, 0, tz).timestamp()
        )


def expand_pattern_lists(pattern, **mappings):
    """
    Expands the pattern for any list-valued mappings, such that for any list of
    length N in the mappings present in the pattern, N copies of the pattern are
    returned, each with an element of the list substituted.

    pattern:
        A pattern to expand, for example ``by-role/{grains[roles]}``

    mappings:
        A dictionary of variables that can be expanded into the pattern.

    Example: Given the pattern `` by-role/{grains[roles]}`` and the below grains

    .. code-block:: yaml

        grains:
            roles:
                - web
                - database

    This function will expand into two patterns,
    ``[by-role/web, by-role/database]``.

    Note that this method does not expand any non-list patterns.
    """
    expanded_patterns = []
    f = string.Formatter()

    # This function uses a string.Formatter to get all the formatting tokens from
    # the pattern, then recursively replaces tokens whose expanded value is a
    # list. For a list with N items, it will create N new pattern strings and
    # then continue with the next token. In practice this is expected to not be
    # very expensive, since patterns will typically involve a handful of lists at
    # most.

    for _, field_name, _, _ in f.parse(pattern):
        if field_name is None:
            continue
        (value, _) = f.get_field(field_name, None, mappings)
        if isinstance(value, list):
            token = f"{{{field_name}}}"
            expanded = [pattern.replace(token, str(elem)) for elem in value]
            for expanded_item in expanded:
                result = expand_pattern_lists(expanded_item, **mappings)
                expanded_patterns += result
            return expanded_patterns
    return [pattern]


def timestring_map(val):
    """
    Turn a time string (like ``60m``) into a float with seconds as a unit.
    """
    if val is None:
        return val
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except ValueError:
        pass
    if not isinstance(val, str):
        raise SaltInvocationError("Expected integer or time string")
    if not re.match(r"^\d+(?:\.\d+)?[smhd]$", val):
        raise SaltInvocationError(f"Invalid time string format: {val}")
    raw, unit = float(val[:-1]), val[-1]
    if unit == "s":
        return raw
    raw *= 60
    if unit == "m":
        return raw
    raw *= 60
    if unit == "h":
        return raw
    raw *= 24
    if unit == "d":
        return raw
    raise RuntimeError("This path should not have been hit")

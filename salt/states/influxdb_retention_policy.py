"""
Management of Influxdb retention policies
=========================================

.. versionadded:: 2017.7.0

(compatible with InfluxDB version 0.9+)
"""


def __virtual__():
    """
    Only load if the influxdb module is available
    """
    if "influxdb.db_exists" in __salt__:
        return "influxdb_retention_policy"
    return (False, "influxdb module could not be loaded")


def convert_duration(duration):
    """
    Convert the a duration string into XXhYYmZZs format

    duration
        Duration to convert

    Returns: duration_string
        String representation of duration in XXhYYmZZs format
    """

    # durations must be specified in days, weeks or hours

    if duration.endswith("h"):
        hours = int(duration.split("h"))

    elif duration.endswith("d"):
        days = duration.split("d")
        hours = int(days[0]) * 24

    elif duration.endswith("w"):
        weeks = duration.split("w")
        hours = int(weeks[0]) * 24 * 7

    duration_string = str(hours) + "h0m0s"
    return duration_string


def present(name, database, duration="7d", replication=1, default=False, **client_args):
    """
    Ensure that given retention policy is present.

    name
        Name of the retention policy to create.

    database
        Database to create retention policy on.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "retention policy {} is already present".format(name),
    }

    if not __salt__["influxdb.retention_policy_exists"](
        name=name, database=database, **client_args
    ):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = " {} is absent and will be created".format(name)
            return ret
        if __salt__["influxdb.create_retention_policy"](
            database, name, duration, replication, default, **client_args
        ):
            ret["comment"] = "retention policy {} has been created".format(name)
            ret["changes"][name] = "Present"
            return ret
        else:
            ret["comment"] = "Failed to create retention policy {}".format(name)
            ret["result"] = False
            return ret

    else:
        current_policy = __salt__["influxdb.get_retention_policy"](
            database=database, name=name, **client_args
        )
        update_policy = False
        if current_policy["duration"] != convert_duration(duration):
            update_policy = True
            ret["changes"]["duration"] = "Retention changed from {} to {}.".format(
                current_policy["duration"], duration
            )

        if current_policy["replicaN"] != replication:
            update_policy = True
            ret["changes"]["replication"] = "Replication changed from {} to {}.".format(
                current_policy["replicaN"], replication
            )

        if current_policy["default"] != default:
            update_policy = True
            ret["changes"]["default"] = "Default changed from {} to {}.".format(
                current_policy["default"], default
            )

        if update_policy:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = " {} is present and set to be changed".format(name)
                return ret
            else:
                if __salt__["influxdb.alter_retention_policy"](
                    database, name, duration, replication, default, **client_args
                ):
                    ret["comment"] = "retention policy {} has been changed".format(name)
                    return ret
                else:
                    ret["comment"] = "Failed to update retention policy {}".format(name)
                    ret["result"] = False
                    return ret

    return ret


def absent(name, database, **client_args):
    """
    Ensure that given retention policy is absent.

    name
        Name of the retention policy to remove.

    database
        Name of the database that the retention policy was defined on.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "retention policy {} is not present".format(name),
    }

    if __salt__["influxdb.retention_policy_exists"](database, name, **client_args):
        if __opts__["test"]:
            ret["result"] = None
            ret[
                "comment"
            ] = "retention policy {} is present and needs to be removed".format(name)
            return ret
        if __salt__["influxdb.drop_retention_policy"](database, name, **client_args):
            ret["comment"] = "retention policy {} has been removed".format(name)
            ret["changes"][name] = "Absent"
            return ret
        else:
            ret["comment"] = "Failed to remove retention policy {}".format(name)
            ret["result"] = False
            return ret

    return ret

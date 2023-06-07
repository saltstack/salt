"""
Management of Open vSwitch database records.

.. versionadded:: 3006.0
"""


def __virtual__():
    """
    Only make these states available if Open vSwitch module is available.
    """
    return "openvswitch.db_get" in __salt__


def managed(name, table, data, record=None):
    """
    Ensures that the specified columns of the named record have the specified
    values.

    Args:
        name : string
            name of the record
        table : string
            name of the table to which the record belongs.
        data : dict
            dictionary containing a mapping from column names to the desired
            values. Columns that exist, but are not specified in this
            dictionary are not touched.
        record : string
            name of the record (optional). Replaces name if specified.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    if record is None:
        record = name
    current_data = {
        column: __salt__["openvswitch.db_get"](table, record, column, True)
        for column in data
    }

    # Comment and change messages
    comment_changes = "Columns have been updated."
    comment_no_changes = "All columns are already up to date."
    comment_error = "Error while updating column {0}: {1}"

    # Dry run, test=true mode
    if __opts__["test"]:
        for column in data:
            if data[column] != current_data[column]:
                ret["changes"][column] = {
                    "old": current_data[column],
                    "new": data[column],
                }
        if ret["changes"]:
            ret["result"] = None
            ret["comment"] = comment_changes
        else:
            ret["result"] = True
            ret["comment"] = comment_no_changes
        return ret

    for column in data:
        if data[column] != current_data[column]:
            result = __salt__["openvswitch.db_set"](table, record, column, data[column])
            if result is not None:
                ret["comment"] = comment_error.format(column, result)
                ret["result"] = False
                return ret
            ret["changes"][column] = {"old": current_data[column], "new": data[column]}
    ret["result"] = True
    ret["comment"] = comment_no_changes
    return ret

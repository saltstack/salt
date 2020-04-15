# -*- coding: utf-8 -*-
"""
Execution of MySQL queries
==========================

.. versionadded:: 2014.7.0

:depends:   - MySQLdb Python module
:configuration: See :py:mod:`salt.modules.mysql` for setup instructions.

The mysql_query module is used to execute queries on MySQL databases.
Its output may be stored in a file or in a grain.

.. code-block:: yaml

    query_id:
      mysql_query.run
        - database: my_database
        - query:    "SELECT * FROM table;"
        - output:   "/tmp/query_id.txt"
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os.path
import sys

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six


def __virtual__():
    """
    Only load if the mysql module is available in __salt__
    """
    return "mysql.query" in __salt__


def _get_mysql_error():
    """
    Look in module context for a MySQL error. Eventually we should make a less
    ugly way of doing this.
    """
    return sys.modules[__salt__["test.ping"].__module__].__context__.pop(
        "mysql.error", None
    )


def run_file(
    name,
    database,
    query_file=None,
    output=None,
    grain=None,
    key=None,
    overwrite=True,
    saltenv=None,
    check_db_exists=True,
    **connection_args
):
    """
    Execute an arbitrary query on the specified database

    .. versionadded:: 2017.7.0

    name
        Used only as an ID

    database
        The name of the database to execute the query_file on

    query_file
        The file of mysql commands to run

    output
        grain: output in a grain
        other: the file to store results
        None:  output to the result comment (default)

    grain:
        grain to store the output (need output=grain)

    key:
        the specified grain will be treated as a dictionary, the result
        of this state will be stored under the specified key.

    overwrite:
        The file or grain will be overwritten if it already exists (default)

    saltenv:
        The saltenv to pull the query_file from

    check_db_exists:
        The state run will check that the specified database exists (default=True)
        before running any queries

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Database {0} is already present".format(database),
    }

    if any(
        [
            query_file.startswith(proto)
            for proto in ["http://", "https://", "salt://", "s3://", "swift://"]
        ]
    ):
        query_file = __salt__["cp.cache_file"](query_file, saltenv=saltenv or __env__)

    if not os.path.exists(query_file):
        ret["comment"] = "File {0} does not exist".format(query_file)
        ret["result"] = False
        return ret

    # check if database exists
    if check_db_exists and not __salt__["mysql.db_exists"](database, **connection_args):
        err = _get_mysql_error()
        if err is not None:
            ret["comment"] = err
            ret["result"] = False
            return ret

        ret["result"] = None
        ret["comment"] = ("Database {0} is not present").format(database)
        return ret

    # Check if execution needed
    if output == "grain":
        if grain is not None and key is None:
            if not overwrite and grain in __salt__["grains.ls"]():
                ret["comment"] = "No execution needed. Grain " + grain + " already set"
                return ret
            elif __opts__["test"]:
                ret["result"] = None
                ret["comment"] = (
                    "Query would execute, storing result in " + "grain: " + grain
                )
                return ret
        elif grain is not None:
            if grain in __salt__["grains.ls"]():
                grain_value = __salt__["grains.get"](grain)
            else:
                grain_value = {}
            if not overwrite and key in grain_value:
                ret["comment"] = (
                    "No execution needed. Grain " + grain + ":" + key + " already set"
                )
                return ret
            elif __opts__["test"]:
                ret["result"] = None
                ret["comment"] = (
                    "Query would execute, storing result in "
                    + "grain: "
                    + grain
                    + ":"
                    + key
                )
                return ret
        else:
            ret["result"] = False
            ret["comment"] = (
                "Error: output type 'grain' needs the grain " + "parameter\n"
            )
            return ret
    elif output is not None:
        if not overwrite and os.path.isfile(output):
            ret["comment"] = "No execution needed. File " + output + " already set"
            return ret
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = (
                "Query would execute, storing result in " + "file: " + output
            )
            return ret
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Query would execute, not storing result"
        return ret

    # The database is present, execute the query
    query_result = __salt__["mysql.file_query"](database, query_file, **connection_args)

    if query_result is False:
        ret["result"] = False
        return ret

    mapped_results = []
    if "results" in query_result:
        for res in query_result["results"]:
            mapped_line = {}
            for idx, col in enumerate(query_result["columns"]):
                mapped_line[col] = res[idx]
            mapped_results.append(mapped_line)
        query_result["results"] = mapped_results

    ret["comment"] = six.text_type(query_result)

    if output == "grain":
        if grain is not None and key is None:
            __salt__["grains.setval"](grain, query_result)
            ret["changes"]["query"] = "Executed. Output into grain: " + grain
        elif grain is not None:
            if grain in __salt__["grains.ls"]():
                grain_value = __salt__["grains.get"](grain)
            else:
                grain_value = {}
            grain_value[key] = query_result
            __salt__["grains.setval"](grain, grain_value)
            ret["changes"]["query"] = (
                "Executed. Output into grain: " + grain + ":" + key
            )
    elif output is not None:
        ret["changes"]["query"] = "Executed. Output into " + output
        with salt.utils.files.fopen(output, "w") as output_file:
            if "results" in query_result:
                for res in query_result["results"]:
                    for col, val in six.iteritems(res):
                        output_file.write(
                            salt.utils.stringutils.to_str(col + ":" + val + "\n")
                        )
            else:
                output_file.write(salt.utils.stringutils.to_str(query_result))
    else:
        ret["changes"]["query"] = "Executed"

    return ret


def run(
    name,
    database,
    query,
    output=None,
    grain=None,
    key=None,
    overwrite=True,
    check_db_exists=True,
    **connection_args
):
    """
    Execute an arbitrary query on the specified database

    name
        Used only as an ID

    database
        The name of the database to execute the query on

    query
        The query to execute

    output
        grain: output in a grain
        other: the file to store results
        None:  output to the result comment (default)

    grain:
        grain to store the output (need output=grain)

    key:
        the specified grain will be treated as a dictionary, the result
        of this state will be stored under the specified key.

    overwrite:
        The file or grain will be overwritten if it already exists (default)

    check_db_exists:
        The state run will check that the specified database exists (default=True)
        before running any queries
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Database {0} is already present".format(database),
    }
    # check if database exists
    if check_db_exists and not __salt__["mysql.db_exists"](database, **connection_args):
        err = _get_mysql_error()
        if err is not None:
            ret["comment"] = err
            ret["result"] = False
            return ret

        ret["result"] = None
        ret["comment"] = ("Database {0} is not present").format(name)
        return ret

    # Check if execution needed
    if output == "grain":
        if grain is not None and key is None:
            if not overwrite and grain in __salt__["grains.ls"]():
                ret["comment"] = "No execution needed. Grain " + grain + " already set"
                return ret
            elif __opts__["test"]:
                ret["result"] = None
                ret["comment"] = (
                    "Query would execute, storing result in " + "grain: " + grain
                )
                return ret
        elif grain is not None:
            if grain in __salt__["grains.ls"]():
                grain_value = __salt__["grains.get"](grain)
            else:
                grain_value = {}
            if not overwrite and key in grain_value:
                ret["comment"] = (
                    "No execution needed. Grain " + grain + ":" + key + " already set"
                )
                return ret
            elif __opts__["test"]:
                ret["result"] = None
                ret["comment"] = (
                    "Query would execute, storing result in "
                    + "grain: "
                    + grain
                    + ":"
                    + key
                )
                return ret
        else:
            ret["result"] = False
            ret["comment"] = (
                "Error: output type 'grain' needs the grain " + "parameter\n"
            )
            return ret
    elif output is not None:
        if not overwrite and os.path.isfile(output):
            ret["comment"] = "No execution needed. File " + output + " already set"
            return ret
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = (
                "Query would execute, storing result in " + "file: " + output
            )
            return ret
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Query would execute, not storing result"
        return ret

    # The database is present, execute the query
    query_result = __salt__["mysql.query"](database, query, **connection_args)
    mapped_results = []
    if "results" in query_result:
        for res in query_result["results"]:
            mapped_line = {}
            for idx, col in enumerate(query_result["columns"]):
                mapped_line[col] = res[idx]
            mapped_results.append(mapped_line)
        query_result["results"] = mapped_results

    ret["comment"] = six.text_type(query_result)

    if output == "grain":
        if grain is not None and key is None:
            __salt__["grains.setval"](grain, query_result)
            ret["changes"]["query"] = "Executed. Output into grain: " + grain
        elif grain is not None:
            if grain in __salt__["grains.ls"]():
                grain_value = __salt__["grains.get"](grain)
            else:
                grain_value = {}
            grain_value[key] = query_result
            __salt__["grains.setval"](grain, grain_value)
            ret["changes"]["query"] = (
                "Executed. Output into grain: " + grain + ":" + key
            )
    elif output is not None:
        ret["changes"]["query"] = "Executed. Output into " + output
        with salt.utils.files.fopen(output, "w") as output_file:
            if "results" in query_result:
                for res in query_result["results"]:
                    for col, val in six.iteritems(res):
                        output_file.write(
                            salt.utils.stringutils.to_str(col + ":" + val + "\n")
                        )
            else:
                if isinstance(query_result, six.text_type):
                    output_file.write(salt.utils.stringutils.to_str(query_result))
                else:
                    for col, val in six.iteritems(query_result):
                        output_file.write(
                            salt.utils.stringutils.to_str("{0}:{1}\n".format(col, val))
                        )
    else:
        ret["changes"]["query"] = "Executed"

    return ret

"""
Manage ini files
================

:maintainer: <akilesh1597@gmail.com>
:maturity: new
:depends: re
:platform: all

"""

from salt.utils.odict import OrderedDict

__virtualname__ = "ini"


def __virtual__():
    """
    Only load if the ini module is available
    """
    return __virtualname__ if "ini.set_option" in __salt__ else False


def options_present(
    name, sections=None, separator="=", strict=False, encoding=None, no_spaces=False
):
    """
    Set or create a key/value pair in an ``ini`` file. Options present in the
    ini file and not specified in the sections dict will be untouched, unless
    the ``strict: True`` flag is used.

    Sections that do not exist will be created.

    Args:

        name (str):
            The path to the ini file

        sections (dict):
            A dictionary of sections and key/value pairs that will be used to
            update the ini file. Other sections and key/value pairs in the ini
            file will be untouched unless ``strict: True`` is passed.

        separator (str):
            The character used to separate keys and values. Standard ini files
            use the "=" character. The default is ``=``.

        strict (bool):
            A boolean value that specifies that the ``sections`` dictionary
            contains all settings in the ini file. ``True`` will create an ini
            file with only the values specified in ``sections``. ``False`` will
            append or update values in an existing ini file and leave the rest
            untouched.

        encoding (str):
            A string value representing encoding of the target ini file. If
            ``None`` is passed, it uses the system default which is likely
            ``utf-8``. Default is ``None``

            .. versionadded:: 3006.10

        no_spaces (bool):
            A bool value that specifies that the key/value separator will be
            wrapped with spaces. This parameter was added to have the ability to
            not wrap the separator with spaces. Default is ``False``, which
            maintains backwards compatibility.

            .. warning::
                This will affect all key/value pairs in the ini file, not just
                the specific value being set.

            .. versionadded:: 3006.10

    Returns:
        dict: A dictionary containing list of changes made

    Example:

    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.options_present:
            - separator: '='
            - strict: True
            - sections:
                test:
                  testkey: 'testval'
                  secondoption: 'secondvalue'
                test1:
                  testkey1: 'testval121'
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "No anomaly detected",
    }
    if __opts__["test"]:
        ret["comment"] = ""
    # pylint: disable=too-many-nested-blocks
    try:
        changes = {}
        if sections:
            options = {}
            for sname, sbody in sections.items():
                if not isinstance(sbody, (dict, OrderedDict)):
                    options.update({sname: sbody})
            cur_ini = __salt__["ini.get_ini"](
                file_name=name, separator=separator, encoding=encoding
            )
            original_top_level_opts = {}
            original_sections = {}
            for key, val in cur_ini.items():
                if isinstance(val, (dict, OrderedDict)):
                    original_sections.update({key: val})
                else:
                    original_top_level_opts.update({key: val})
            if __opts__["test"]:
                for option in options:
                    if option in original_top_level_opts:
                        if str(original_top_level_opts[option]) == str(options[option]):
                            ret["comment"] += f"Unchanged key {option}.\n"
                        else:
                            ret["comment"] += f"Changed key {option}.\n"
                            ret["result"] = None
                    else:
                        ret["comment"] += f"Changed key {option}.\n"
                        ret["result"] = None
            else:
                options_updated = __salt__["ini.set_option"](
                    file_name=name,
                    sections=options,
                    separator=separator,
                    encoding=encoding,
                    no_spaces=no_spaces,
                )
                changes.update(options_updated)
            if strict:
                for opt_to_remove in set(original_top_level_opts).difference(options):
                    if __opts__["test"]:
                        ret["comment"] += f"Removed key {opt_to_remove}.\n"
                        ret["result"] = None
                    else:
                        __salt__["ini.remove_option"](
                            file_name=name,
                            section=None,
                            option=opt_to_remove,
                            separator=separator,
                            encoding=encoding,
                        )
                        changes.update(
                            {
                                opt_to_remove: {
                                    "before": original_top_level_opts[opt_to_remove],
                                    "after": None,
                                }
                            }
                        )
            for section_name, section_body in [
                (sname, sbody)
                for sname, sbody in sections.items()
                if isinstance(sbody, (dict, OrderedDict))
            ]:
                section_descr = " in section " + section_name if section_name else ""
                changes[section_name] = {}
                if strict:
                    original = cur_ini.get(section_name, {})
                    for key_to_remove in set(original.keys()).difference(
                        section_body.keys()
                    ):
                        orig_value = original_sections.get(section_name, {}).get(
                            key_to_remove, "#-#-"
                        )
                        if __opts__["test"]:
                            ret["comment"] += "Deleted key {}{}.\n".format(
                                key_to_remove, section_descr
                            )
                            ret["result"] = None
                        else:
                            __salt__["ini.remove_option"](
                                file_name=name,
                                section=section_name,
                                option=key_to_remove,
                                separator=separator,
                                encoding=encoding,
                            )
                            changes[section_name].update({key_to_remove: ""})
                            changes[section_name].update(
                                {key_to_remove: {"before": orig_value, "after": None}}
                            )
                if __opts__["test"]:
                    for option in section_body:
                        if str(section_body[option]) == str(
                            original_sections.get(section_name, {}).get(option, "#-#-")
                        ):
                            ret["comment"] += "Unchanged key {}{}.\n".format(
                                option, section_descr
                            )
                        else:
                            ret["comment"] += "Changed key {}{}.\n".format(
                                option, section_descr
                            )
                            ret["result"] = None
                else:
                    options_updated = __salt__["ini.set_option"](
                        file_name=name,
                        sections={section_name: section_body},
                        separator=separator,
                        encoding=encoding,
                        no_spaces=no_spaces,
                    )
                    if options_updated:
                        changes[section_name].update(options_updated[section_name])
                    if not changes[section_name]:
                        del changes[section_name]
        else:
            if not __opts__["test"]:
                changes = __salt__["ini.set_option"](
                    file_name=name,
                    sections=sections,
                    separator=separator,
                    encoding=encoding,
                    no_spaces=no_spaces,
                )
    except (OSError, KeyError) as err:
        ret["comment"] = f"{err}"
        ret["result"] = False
        return ret
    if "error" in changes:
        ret["result"] = False
        ret["comment"] = "Errors encountered. {}".format(changes["error"])
        ret["changes"] = {}
    else:
        for ciname, body in changes.items():
            if body:
                ret["comment"] = "Changes take effect"
                ret["changes"].update({ciname: changes[ciname]})
    return ret


def options_absent(name, sections=None, separator="=", encoding=None):
    """
    Remove a key/value pair from an ini file. Key/value pairs present in the ini
    file and not specified in sections dict will be untouched.

    Args:

        name (str):
            The path to the ini file

        sections (dict):
            A dictionary of sections and key/value pairs that will be removed
            from the ini file. Other key/value pairs in the ini file will be
            untouched.

        separator (str):
            The character used to separate keys and values. Standard ini files
            use the "=" character. The default is ``=``.

        encoding (str):
            A string value representing encoding of the target ini file. If
            ``None`` is passed, it uses the system default which is likely
            ``utf-8``. Default is ``None``

            .. versionadded:: 3006.10

    Returns:
        dict: A dictionary containing list of changes made

    Example:

    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.options_absent:
            - separator: '='
            - sections:
                test:
                  - testkey
                  - secondoption
                test1:
                  - testkey1
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "No anomaly detected",
    }
    if __opts__["test"]:
        ret["result"] = True
        ret["comment"] = ""
        for section in sections or {}:
            section_name = " in section " + section if section else ""
            try:
                cur_section = __salt__["ini.get_section"](
                    file_name=name,
                    section=section,
                    separator=separator,
                    encoding=encoding,
                )
            except OSError as err:
                ret["comment"] = f"{err}"
                ret["result"] = False
                return ret
            except AttributeError:
                cur_section = section
            if isinstance(sections[section], list):
                for key in sections[section]:
                    cur_value = cur_section.get(key)
                    if not cur_value:
                        ret["comment"] += "Key {}{} does not exist.\n".format(
                            key, section_name
                        )
                        continue
                    ret["comment"] += f"Deleted key {key}{section_name}.\n"
                    ret["result"] = None
            else:
                option = section
                if not __salt__["ini.get_option"](
                    file_name=name,
                    section=None,
                    option=option,
                    separator=separator,
                    encoding=encoding,
                ):
                    ret["comment"] += f"Key {option} does not exist.\n"
                    continue
                ret["comment"] += f"Deleted key {option}.\n"
                ret["result"] = None

        if ret["comment"] == "":
            ret["comment"] = "No changes detected."
        return ret
    sections = sections or {}
    for section, keys in sections.items():
        for key in keys:
            try:
                current_value = __salt__["ini.remove_option"](
                    file_name=name,
                    section=section,
                    option=key,
                    separator=separator,
                    encoding=encoding,
                )
            except OSError as err:
                ret["comment"] = f"{err}"
                ret["result"] = False
                return ret
            if not current_value:
                continue
            if section not in ret["changes"]:
                ret["changes"].update({section: {}})
            ret["changes"][section].update({key: current_value})
            if not isinstance(sections[section], list):
                ret["changes"].update({section: current_value})
                # break
            ret["comment"] = "Changes take effect"
    return ret


def sections_present(name, sections=None, separator="=", encoding=None):
    """
    Add sections to an ini file. This will only create empty sections. To also
    create key/value pairs, use options_present state.

    Args:

        name (str):
            The path to the ini file

        sections (dict):
            A dictionary of sections and key/value pairs that will be used to
            update the ini file. Only the sections portion is used, key/value
            pairs are ignored. To also set key/value pairs, use the
            options_present state.

        separator (str):
            The character used to separate keys and values. Standard ini files
            use the "=" character. The default is ``=``.

        encoding (str):
            A string value representing encoding of the target ini file. If
            ``None`` is passed, it uses the system default which is likely
            ``utf-8``. Default is ``None``

            .. versionadded:: 3006.10

    Returns:
        dict: A dictionary containing list of changes made

    Example:

    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_present:
            - separator: '='
            - sections:
                - section_one
                - section_two
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "No anomaly detected",
    }
    if __opts__["test"]:
        ret["result"] = True
        ret["comment"] = ""
        try:
            cur_ini = __salt__["ini.get_ini"](
                file_name=name, separator=separator, encoding=encoding
            )
        except OSError as err:
            ret["result"] = False
            ret["comment"] = f"{err}"
            return ret
        for section in sections or {}:
            if section in cur_ini:
                ret["comment"] += f"Section unchanged {section}.\n"
                continue
            else:
                ret["comment"] += f"Created new section {section}.\n"
            ret["result"] = None
        if ret["comment"] == "":
            ret["comment"] = "No changes detected."
        return ret
    section_to_update = {}
    for section_name in sections or []:
        section_to_update.update({section_name: {}})
    try:
        changes = __salt__["ini.set_option"](
            file_name=name,
            section=section_to_update,
            separator=separator,
            encoding=encoding,
        )
    except OSError as err:
        ret["result"] = False
        ret["comment"] = f"{err}"
        return ret
    if "error" in changes:
        ret["result"] = False
        ret["changes"] = "Errors encountered {}".format(changes["error"])
        return ret
    ret["changes"] = changes
    ret["comment"] = "Changes take effect"
    return ret


def sections_absent(name, sections=None, separator="=", encoding=None):
    """
    Remove sections from the ini file. All key/value pairs in the section will
    also be removed.

    Args:

        name (str):
            The path to the ini file

        sections (dict):
            A dictionary of sections and key/value pairs that will be used to
            update the ini file. Other sections and key/value pairs in the ini
            file will be untouched unless ``strict: True`` is passed.

        separator (str):
            The character used to separate keys and values. Standard ini files
            use the "=" character. The default is ``=``.

        encoding (str):
            A string value representing encoding of the target ini file. If
            ``None`` is passed, it uses the system default which is likely
            ``utf-8``. Default is ``None``

            .. versionadded:: 3006.6

    Returns:
        dict: A dictionary containing list of changes made

    Example:

    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_absent:
            - separator: '='
            - sections:
                - test
                - test1
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "No anomaly detected",
    }
    if __opts__["test"]:
        ret["result"] = True
        ret["comment"] = ""
        try:
            cur_ini = __salt__["ini.get_ini"](
                file_name=name, separator=separator, encoding=encoding
            )
        except OSError as err:
            ret["result"] = False
            ret["comment"] = f"{err}"
            return ret
        for section in sections or []:
            if section not in cur_ini:
                ret["comment"] += f"Section {section} does not exist.\n"
                continue
            ret["comment"] += f"Deleted section {section}.\n"
            ret["result"] = None
        if ret["comment"] == "":
            ret["comment"] = "No changes detected."
        return ret
    for section in sections or []:
        try:
            cur_section = __salt__["ini.remove_section"](
                file_name=name, section=section, separator=separator, encoding=encoding
            )
        except OSError as err:
            ret["result"] = False
            ret["comment"] = f"{err}"
            return ret
        if not cur_section:
            continue
        ret["changes"][section] = cur_section
        ret["comment"] = "Changes take effect"
    return ret

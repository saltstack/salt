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


def options_present(name, sections=None, separator="=", strict=False):
    """
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

    options present in file and not specified in sections
    dict will be untouched, unless `strict: True` flag is
    used

    changes dict will contain the list of changes made
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
            cur_ini = __salt__["ini.get_ini"](name, separator)
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
                            ret["comment"] += "Unchanged key {}.\n".format(option)
                        else:
                            ret["comment"] += "Changed key {}.\n".format(option)
                            ret["result"] = None
                    else:
                        ret["comment"] += "Changed key {}.\n".format(option)
                        ret["result"] = None
            else:
                options_updated = __salt__["ini.set_option"](name, options, separator)
                changes.update(options_updated)
            if strict:
                for opt_to_remove in set(original_top_level_opts).difference(options):
                    if __opts__["test"]:
                        ret["comment"] += "Removed key {}.\n".format(opt_to_remove)
                        ret["result"] = None
                    else:
                        __salt__["ini.remove_option"](
                            name, None, opt_to_remove, separator
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
                                name, section_name, key_to_remove, separator
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
                        name, {section_name: section_body}, separator
                    )
                    if options_updated:
                        changes[section_name].update(options_updated[section_name])
                    if not changes[section_name]:
                        del changes[section_name]
        else:
            if not __opts__["test"]:
                changes = __salt__["ini.set_option"](name, sections, separator)
    except (OSError, KeyError) as err:
        ret["comment"] = "{}".format(err)
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


def options_absent(name, sections=None, separator="="):
    """
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

    options present in file and not specified in sections
    dict will be untouched

    changes dict will contain the list of changes made
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
                cur_section = __salt__["ini.get_section"](name, section, separator)
            except OSError as err:
                ret["comment"] = "{}".format(err)
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
                    ret["comment"] += "Deleted key {}{}.\n".format(key, section_name)
                    ret["result"] = None
            else:
                option = section
                if not __salt__["ini.get_option"](name, None, option, separator):
                    ret["comment"] += "Key {} does not exist.\n".format(option)
                    continue
                ret["comment"] += "Deleted key {}.\n".format(option)
                ret["result"] = None

        if ret["comment"] == "":
            ret["comment"] = "No changes detected."
        return ret
    sections = sections or {}
    for section, keys in sections.items():
        for key in keys:
            try:
                current_value = __salt__["ini.remove_option"](
                    name, section, key, separator
                )
            except OSError as err:
                ret["comment"] = "{}".format(err)
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


def sections_present(name, sections=None, separator="="):
    """
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_present:
            - separator: '='
            - sections:
                - section_one
                - section_two

    This will only create empty sections. To also create options, use
    options_present state

    options present in file and not specified in sections will be deleted
    changes dict will contain the sections that changed
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
            cur_ini = __salt__["ini.get_ini"](name, separator)
        except OSError as err:
            ret["result"] = False
            ret["comment"] = "{}".format(err)
            return ret
        for section in sections or {}:
            if section in cur_ini:
                ret["comment"] += "Section unchanged {}.\n".format(section)
                continue
            else:
                ret["comment"] += "Created new section {}.\n".format(section)
            ret["result"] = None
        if ret["comment"] == "":
            ret["comment"] = "No changes detected."
        return ret
    section_to_update = {}
    for section_name in sections or []:
        section_to_update.update({section_name: {}})
    try:
        changes = __salt__["ini.set_option"](name, section_to_update, separator)
    except OSError as err:
        ret["result"] = False
        ret["comment"] = "{}".format(err)
        return ret
    if "error" in changes:
        ret["result"] = False
        ret["changes"] = "Errors encountered {}".format(changes["error"])
        return ret
    ret["changes"] = changes
    ret["comment"] = "Changes take effect"
    return ret


def sections_absent(name, sections=None, separator="="):
    """
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_absent:
            - separator: '='
            - sections:
                - test
                - test1

    options present in file and not specified in sections will be deleted
    changes dict will contain the sections that changed
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
            cur_ini = __salt__["ini.get_ini"](name, separator)
        except OSError as err:
            ret["result"] = False
            ret["comment"] = "{}".format(err)
            return ret
        for section in sections or []:
            if section not in cur_ini:
                ret["comment"] += "Section {} does not exist.\n".format(section)
                continue
            ret["comment"] += "Deleted section {}.\n".format(section)
            ret["result"] = None
        if ret["comment"] == "":
            ret["comment"] = "No changes detected."
        return ret
    for section in sections or []:
        try:
            cur_section = __salt__["ini.remove_section"](name, section, separator)
        except OSError as err:
            ret["result"] = False
            ret["comment"] = "{}".format(err)
            return ret
        if not cur_section:
            continue
        ret["changes"][section] = cur_section
        ret["comment"] = "Changes take effect"
    return ret

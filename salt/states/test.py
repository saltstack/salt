"""
Test States
===========

Provide test case states that enable easy testing of things to do with state
calls, e.g. running, calling, logging, output filtering etc.

.. code-block:: yaml

    always-passes-with-any-kwarg:
      test.nop:
        - name: foo
        - something: else
        - foo: bar

    always-passes:
      test.succeed_without_changes:
        - name: foo

    always-fails:
      test.fail_without_changes:
        - name: foo

    always-changes-and-succeeds:
      test.succeed_with_changes:
        - name: foo

    always-changes-and-fails:
      test.fail_with_changes:
        - name: foo

    my-custom-combo:
      test.configurable_test_state:
        - name: foo
        - changes: True
        - result: False
        - comment: bar.baz
        - warnings: A warning

    is-pillar-foo-present-and-bar-is-int:
      test.check_pillar:
        - present:
            - foo
        - integer:
            - bar

You may also use these states for controlled failure in state definitions, for example if certain conditions in
pillar or grains do not apply. The following state definition will fail with a message "OS not supported!" when
`grains['os']` is neither Ubuntu nor CentOS:

.. code-block:: jinja

    {% if grains['os'] in ['Ubuntu', 'CentOS'] %}

    # Your state definitions go here

    {% else %}
    failure:
      test.fail_without_changes:
        - name: "OS not supported!"
        - failhard: True
    {% endif %}

"""

import random

import salt.utils.data
from salt.exceptions import SaltInvocationError
from salt.state import _gen_tag


def nop(name, **kwargs):
    """
    .. versionadded:: 2015.8.1

    A no-op state that does nothing. Useful in conjunction with the ``use``
    requisite, or in templates which could otherwise be empty due to jinja
    rendering.

    name
        A unique string to serve as the state's ID
    """
    return succeed_without_changes(name)


def succeed_without_changes(name, **kwargs):  # pylint: disable=unused-argument
    """
    .. versionadded:: 2014.7.0

    Returns successful

    name
        A unique string to serve as the state's ID
    """
    comment = kwargs.get("comment", "Success!")

    ret = {"name": name, "changes": {}, "result": True, "comment": comment}
    return ret


def fail_without_changes(name, **kwargs):  # pylint: disable=unused-argument
    """
    .. versionadded:: 2014.7.0

    Returns failure

    name
        A unique string to serve as the state's ID
    """
    comment = kwargs.get("comment", "Failure!")

    ret = {"name": name, "changes": {}, "result": False, "comment": comment}

    if __opts__["test"]:
        ret["result"] = False
        ret["comment"] = "If we weren't testing, this would be a failure!"

    return ret


def succeed_with_changes(name, **kwargs):  # pylint: disable=unused-argument
    """
    .. versionadded:: 2014.7.0

    Returns ``True`` with an non-empty ``changes`` dictionary. Useful for
    testing requisites.

    name
        A unique string to serve as the state's ID
    """
    comment = kwargs.get("comment", "Success!")

    ret = {"name": name, "changes": {}, "result": True, "comment": comment}

    # Following the docs as written here
    # https://docs.saltproject.io/ref/states/writing.html#return-data
    ret["changes"] = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "If we weren't testing, this would be successful with changes"

    return ret


def fail_with_changes(name, **kwargs):  # pylint: disable=unused-argument
    """
    .. versionadded:: 2014.7.0

    Returns ``False`` with an non-empty ``changes`` dictionary. Useful for
    testing requisites.

    name
        A unique string to serve as the state's ID
    """
    comment = kwargs.get("comment", "Failure!")

    ret = {"name": name, "changes": {}, "result": False, "comment": comment}

    # Following the docs as written here
    # https://docs.saltproject.io/ref/states/writing.html#return-data
    ret["changes"] = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "If we weren't testing, this would be failed with changes"

    return ret


def configurable_test_state(name, changes=True, result=True, comment="", warnings=None):
    """
    .. versionadded:: 2014.7.0

    A configurable test state which allows for more control over the return
    data

    name
        A unique string to serve as the state's ID

    changes : True
        Controls whether or not the state reports that there were changes.
        There are three supported values for this argument:

        - If ``True``, the state will report changes
        - If ``False``, the state will report no changes
        - If ``"Random"``, the state will randomly report either changes or no
          changes.

    result : True
        Controls the result for for the state. Like ``changes``, there are
        three supported values for this argument:

        - If ``True``, the state will report a ``True`` result
        - If ``False``, the state will report a ``False`` result
        - If ``"Random"``, the state will randomly report either ``True``

        .. note::
            The result will be reported as ``None`` if *all* of the following
            are true:

            1. The state is being run in test mode (i.e. ``test=True`` on the
            CLI)

            2. ``result`` is ``True`` (either explicitly, or via being set to
               ``"Random"``)

            3. ``changes`` is ``True`` (either explicitly, or via being set to
               ``"Random"``)

    comment : ""
        Comment field field for the state. By default, this is an empty string.

    warnings
        A string (or a list of strings) to fill the warnings field with.
        Default is None

        .. versionadded:: 3000
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": comment}
    change_data = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    if changes is True:
        # If changes is True we place our dummy change dictionary into it.
        # Following the docs as written here
        # https://docs.saltproject.io/ref/states/writing.html#return-data
        ret["changes"] = change_data
    elif changes is False:
        # Don't modify changes from the "ret" dict set above
        pass
    else:
        if str(changes).lower() == "random":
            if random.choice((True, False)):
                # Following the docs as written here
                # https://docs.saltproject.io/ref/states/writing.html#return-data
                ret["changes"] = change_data
        else:
            err = (
                "You have specified the state option 'changes' with "
                "invalid arguments. It must be either "
                "True, False, or 'Random'"
            )
            raise SaltInvocationError(err)

    if isinstance(result, bool):
        ret["result"] = result
    else:
        if str(result).lower() == "random":
            ret["result"] = random.choice((True, False))
        else:
            raise SaltInvocationError(
                "You have specified the state option "
                "'result' with invalid arguments. It must "
                "be either True, False, or "
                "'Random'"
            )

    if warnings is None:
        pass
    elif isinstance(warnings, str):
        ret["warnings"] = [warnings]
    elif isinstance(warnings, list):
        ret["warnings"] = warnings
    else:
        raise SaltInvocationError(
            "You have specified the state option "
            "'warnings' with invalid arguments. It must "
            "be a string or a list of strings"
        )

    if __opts__["test"]:
        ret["result"] = True if changes is False else None
        ret["comment"] = "This is a test" if not comment else comment

    return ret


def show_notification(name, text=None, **kwargs):
    """
    .. versionadded:: 2015.8.0

    Simple notification using text argument.

    name
        A unique string to serve as the state's ID

    text
        Text to return in the comment field
    """

    if not text:
        raise SaltInvocationError("Missing required argument text.")

    ret = {"name": name, "changes": {}, "result": True, "comment": text}

    return ret


def mod_watch(name, sfun=None, **kwargs):
    """
    Call this function via a watch statement

    .. versionadded:: 2014.7.0

    Any parameters in the state return dictionary can be customized by adding
    the keywords ``result``, ``comment``, and ``changes``.

    .. code-block:: yaml

        this_state_will_return_changes:
          test.succeed_with_changes

        this_state_will_NOT_return_changes:
          test.succeed_without_changes

        this_state_is_watching_another_state:
          test.succeed_without_changes:
            - comment: 'This is a custom comment'
            - watch:
              - test: this_state_will_return_changes
              - test: this_state_will_NOT_return_changes

        this_state_is_also_watching_another_state:
          test.succeed_without_changes:
            - watch:
              - test: this_state_will_NOT_return_changes
    """
    has_changes = []
    if "__reqs__" in __low__:
        for req in __low__["__reqs__"]["watch"]:
            tag = _gen_tag(req)
            if __running__[tag]["changes"]:
                has_changes.append("{state}: {__id__}".format(**req))

    ret = {
        "name": name,
        "result": kwargs.get("result", True),
        "comment": kwargs.get("comment", "Watch statement fired."),
        "changes": kwargs.get("changes", {"Requisites with changes": has_changes}),
    }
    return ret


def _check_key_type(key_str, key_type=None):
    """
    Helper function to get pillar[key_str] and
    check if its type is key_type

    Returns None if the pillar key is missing.
    If present True or False depending on match
    of the values type.

    Can't check for None.
    """
    value = __salt__["pillar.get"](key_str, None)
    if value is None:
        return None
    elif key_type is not None and not isinstance(value, key_type):
        return False
    else:
        return True


def _if_str_then_list(listing):
    """
    Checks if its argument is a list or a str.
    A str will be turned into a list with the
    str as its only element.
    """
    if isinstance(listing, str):
        return [salt.utils.stringutils.to_unicode(listing)]
    elif not isinstance(listing, list):
        raise TypeError
    return salt.utils.data.decode_list(listing)


def check_pillar(
    name,
    present=None,
    boolean=None,
    integer=None,
    string=None,
    listing=None,
    dictionary=None,
    verbose=False,
):
    """
    Checks the presence and, optionally, the type of given keys in Pillar

    Supported kwargs for types are:
    - boolean (bool)
    - integer (int)
    - string (str)
    - listing (list)
    - dictionary (dict)

    Checking for None type pillars is not implemented yet.

    .. code-block:: yaml

        is-pillar-foo-present-and-bar-is-int:
          test.check_pillar:
            - present:
                - foo
            - integer:
                - bar
    """
    if not (present or boolean or integer or string or listing or dictionary):
        raise SaltInvocationError("Missing required argument text.")

    present = present or []
    boolean = boolean or []
    integer = integer or []
    string = string or []
    listing = listing or []
    dictionary = dictionary or []

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    checks = {}
    fine = {}
    failed = {}
    # for those we don't check the type:
    present = _if_str_then_list(present)
    checks[None] = present
    # those should be bool:
    boolean = _if_str_then_list(boolean)
    checks[bool] = boolean
    # those should be int:

    # those should be integer:
    integer = _if_str_then_list(integer)
    checks[int] = integer
    # those should be str:
    string = _if_str_then_list(string)
    checks[(str,)] = string
    # those should be list:
    listing = _if_str_then_list(listing)
    checks[list] = listing
    # those should be dict:
    dictionary = _if_str_then_list(dictionary)
    checks[dict] = dictionary

    for key_type, keys in checks.items():
        for key in keys:
            result = _check_key_type(key, key_type)
            if result is None:
                failed[key] = None
                ret["result"] = False
            elif not result:
                failed[key] = key_type
                ret["result"] = False
            elif verbose:
                fine[key] = key_type

    for key, key_type in failed.items():
        comment = 'Pillar key "{}" '.format(key)
        if key_type is None:
            comment += "is missing.\n"
        else:
            comment += "is not {}.\n".format(key_type)
        ret["comment"] += comment

    if verbose and fine:
        comment = "Those keys passed the check:\n"
        for key, key_type in fine.items():
            comment += "- {} ({})\n".format(key, key_type)
        ret["comment"] += comment

    return ret

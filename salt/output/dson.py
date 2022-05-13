"""
Display return data in DSON format
==================================

This outputter is intended for demonstration purposes. Information on the DSON
spec can be found `here`__.

.. __: http://vpzomtrrfrt.github.io/DSON/

This outputter requires `Dogeon`__ (installable via pip)

.. __: https://github.com/soasme/dogeon
"""

import logging

try:
    import dson
except ImportError:
    dson = None


log = logging.getLogger(__name__)


def __virtual__():
    if dson is None:
        return (False, "The dogeon Python package is not installed")
    return True


def output(data, **kwargs):  # pylint: disable=unused-argument
    """
    Print the output data in JSON
    """
    try:
        dump_opts = {"indent": 4, "default": repr}

        if "output_indent" in __opts__:

            indent = __opts__.get("output_indent")
            sort_keys = False

            if indent == "pretty":
                indent = 4
                sort_keys = True

            elif isinstance(indent, int):
                if indent < 0:
                    indent = None

            dump_opts["indent"] = indent
            dump_opts["sort_keys"] = sort_keys

        return dson.dumps(data, **dump_opts)

    except UnicodeDecodeError as exc:
        log.error("Unable to serialize output to dson")
        return dson.dumps(
            {"error": "Unable to serialize output to DSON", "message": str(exc)}
        )

    except TypeError:
        log.debug("An error occurred while outputting DSON", exc_info=True)
    # Return valid JSON for unserializable objects
    return dson.dumps({})

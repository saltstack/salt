# -*- coding: utf-8 -*-
"""
Module for checking jinja maps and verifying the result of loading JSON/YAML
files

.. versionadded:: 3000
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import functools
import logging
import textwrap

# Import Salt libs
import salt.loader
import salt.template
import salt.utils.json

log = logging.getLogger(__name__)


def _strip_odict(wrapped):
    """
    dump to json and load it again, replaces OrderedDicts with regular ones
    """

    @functools.wraps(wrapped)
    def strip(*args):
        return salt.utils.json.loads(salt.utils.json.dumps(wrapped(*args)))

    return strip


@_strip_odict
def load_map(path, value):
    """
    Loads the map at the specified path, and returns the specified value from
    that map.

    CLI Example:

    .. code-block:: bash

        # Assuming the map is loaded in your formula SLS as follows:
        #
        # {% from "myformula/map.jinja" import myformula with context %}
        #
        # the following syntax can be used to load the map and check the
        # results:
        salt myminion jinja.load_map myformula/map.jinja myformula
    """
    tmplstr = textwrap.dedent(
        """\
        {{% from "{path}" import {value} with context %}}
        {{{{ {value} | tojson }}}}
        """.format(
            path=path, value=value
        )
    )
    return salt.template.compile_template_str(
        tmplstr,
        salt.loader.render(__opts__, __salt__),
        __opts__["renderer"],
        __opts__["renderer_blacklist"],
        __opts__["renderer_whitelist"],
    )


@_strip_odict
def import_yaml(path):
    """
    Loads YAML data from the specified path

    CLI Example:

    .. code-block:: bash

        salt myminion jinja.import_yaml myformula/foo.yaml
    """
    tmplstr = textwrap.dedent(
        """\
        {{% import_yaml "{path}" as imported %}}
        {{{{ imported | tojson }}}}
        """.format(
            path=path
        )
    )
    return salt.template.compile_template_str(
        tmplstr,
        salt.loader.render(__opts__, __salt__),
        __opts__["renderer"],
        __opts__["renderer_blacklist"],
        __opts__["renderer_whitelist"],
    )


@_strip_odict
def import_json(path):
    """
    Loads JSON data from the specified path

    CLI Example:

    .. code-block:: bash

        salt myminion jinja.import_JSON myformula/foo.json
    """
    tmplstr = textwrap.dedent(
        """\
        {{% import_json "{path}" as imported %}}
        {{{{ imported | tojson }}}}
        """.format(
            path=path
        )
    )
    return salt.template.compile_template_str(
        tmplstr,
        salt.loader.render(__opts__, __salt__),
        __opts__["renderer"],
        __opts__["renderer_blacklist"],
        __opts__["renderer_whitelist"],
    )

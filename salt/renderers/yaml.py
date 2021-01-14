# -*- coding: utf-8 -*-
"""
YAML Renderer for Salt

For YAML usage information see :ref:`Understanding YAML <yaml>`.
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import warnings

# Import salt libs
import salt.utils.url
import salt.utils.yamlloader as yamlloader_new
import salt.utils.yamlloader_old as yamlloader_old
from salt.exceptions import SaltRenderError
from salt.ext import six
from salt.ext.six import string_types
from salt.utils.odict import OrderedDict
from yaml.constructor import ConstructorError
from yaml.parser import ParserError
from yaml.scanner import ScannerError

log = logging.getLogger(__name__)

_ERROR_MAP = {
    ("found character '\\t' that cannot " "start any token"): "Illegal tab character"
}


def get_yaml_loader(argline):
    """
    Return the ordered dict yaml loader
    """

    def yaml_loader(*args):
        if __opts__.get("use_yamlloader_old"):
            yamlloader = yamlloader_old
        else:
            yamlloader = yamlloader_new
        return yamlloader.SaltYamlSafeLoader(*args, dictclass=OrderedDict)

    return yaml_loader


def render(yaml_data, saltenv="base", sls="", argline="", **kws):
    """
    Accepts YAML as a string or as a file object and runs it through the YAML
    parser.

    :rtype: A Python data structure
    """
    if __opts__.get("use_yamlloader_old"):
        log.warning(
            "Using the old YAML Loader for rendering, "
            "consider disabling this and using the tojson"
            " filter."
        )
        yamlloader = yamlloader_old
    else:
        yamlloader = yamlloader_new
    if not isinstance(yaml_data, string_types):
        yaml_data = yaml_data.read()
    with warnings.catch_warnings(record=True) as warn_list:
        try:
            data = yamlloader.load(yaml_data, Loader=get_yaml_loader(argline))
        except ScannerError as exc:
            err_type = _ERROR_MAP.get(exc.problem, exc.problem)
            line_num = exc.problem_mark.line + 1
            raise SaltRenderError(err_type, line_num, exc.problem_mark.buffer)
        except (ParserError, ConstructorError) as exc:
            raise SaltRenderError(exc)
        if len(warn_list) > 0:
            for item in warn_list:
                log.warning(
                    "%s found in %s saltenv=%s",
                    item.message,
                    salt.utils.url.create(sls),
                    saltenv,
                )
        if not data:
            data = {}
        log.debug("Results of YAML rendering: \n%s", data)

        def _validate_data(data):
            """
            PyYAML will for some reason allow improper YAML to be formed into
            an unhashable dict (that is, one with a dict as a key). This
            function will recursively go through and check the keys to make
            sure they're not dicts.
            """
            if isinstance(data, dict):
                for key, value in six.iteritems(data):
                    if isinstance(key, dict):
                        raise SaltRenderError(
                            "Invalid YAML, possible double curly-brace"
                        )
                    _validate_data(value)
            elif isinstance(data, list):
                for item in data:
                    _validate_data(item)

        _validate_data(data)
        return data

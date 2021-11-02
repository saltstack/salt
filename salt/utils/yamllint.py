import logging

import salt.utils.stringutils

HAS_YAMLLINT = True
try:
    from yamllint import linter
    from yamllint.config import YamlLintConfig
except ImportError:
    HAS_YAMLLINT = False

log = logging.getLogger(__name__)

__virtualname__ = "yamllint"


def __virtual__():
    if HAS_YAMLLINT:
        return __virtualname__
    else:
        return (False, "YAMLLint Not installed")


def lint(
    source,
    yamlconf=None,
):
    """
    lint yaml and return result.
    source (required)
        yaml as str
    yamlconf (optional)
        yamllint config file to use, if not set will default to a extended relaxed format.
    """

    if yamlconf is not None:
        conf = YamlLintConfig(file=yamlconf)
    else:
        conf = YamlLintConfig("extends: relaxed")

    yaml_out = salt.utils.stringutils.to_str(source)
    problems = []
    for problem in linter.run(yaml_out, conf):
        problems.append(
            {
                "line": problem.line,
                "column": problem.column,
                "level": problem.level,
                "comment": problem.message,
            }
        )
    output = {"source": yaml_out, "problems": problems}
    return output

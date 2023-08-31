import logging

import salt.utils.stringutils

try:
    import yamllint
    from yamllint import linter
    from yamllint.config import YamlLintConfig

    HAS_YAMLLINT = True
except ImportError:
    HAS_YAMLLINT = False

log = logging.getLogger(__name__)


def has_yamllint():
    """
    report if yamllint could be imported safly. allowing for clean import detection
    """
    return HAS_YAMLLINT


def version():
    """
    report version of yamllint installed for version comparison
    """
    return yamllint.__version__


def lint(
    source,
    yamlconf=None,
):
    """
    lint yaml and return result.
    source (required)
        yaml as str
    yamlconf (optional)
        yamllint config file to use, if not set will default to a salty version of realaxed.
    """

    if yamlconf is not None:
        conf = YamlLintConfig(file=yamlconf)
    else:
        yamlconf = """
        extends: relaxed
        rules:
          line-length: { max: 256, level: warning }
          empty-lines: disable
          empty-values: {forbid-in-block-mappings: false, forbid-in-flow-mappings: true}
          trailing-spaces: disable
          key-ordering: disable
        """
        conf = YamlLintConfig(yamlconf)

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

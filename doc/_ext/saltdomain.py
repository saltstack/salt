import itertools
import os
import re

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import ViewList
from sphinx import addnodes
from sphinx.domains import ObjType
from sphinx.domains import python as python_domain
from sphinx.domains.python import PyObject
from sphinx.locale import _
from sphinx.roles import XRefRole
from sphinx.util.nodes import make_refnode, nested_parse_with_titles, set_source_info

import salt


class Event(PyObject):
    """
    Document Salt events
    """

    domain = "salt"


class LiterateCoding(Directive):
    """
    Auto-doc SLS files using literate-style comment/code separation
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False

    def parse_file(self, fpath):
        """
        Read a file on the file system (relative to salt's base project dir)

        :returns: A file-like object.
        :raises IOError: If the file cannot be found or read.
        """
        sdir = os.path.abspath(os.path.join(os.path.dirname(salt.__file__), os.pardir))
        with open(os.path.join(sdir, fpath), "rb") as f:
            return f.readlines()

    def parse_lit(self, lines):
        """
        Parse a string line-by-line delineating comments and code

        :returns: An tuple of boolean/list-of-string pairs. True designates a
            comment; False designates code.
        """
        comment_char = "#"  # TODO: move this into a directive option
        comment = re.compile(rf"^\s*{comment_char}[ \n]")
        section_test = lambda val: bool(comment.match(val))

        sections = []
        for is_doc, group in itertools.groupby(lines, section_test):
            if is_doc:
                text = [comment.sub("", i).rstrip("\r\n") for i in group]
            else:
                text = [i.rstrip("\r\n") for i in group]

            sections.append((is_doc, text))

        return sections

    def run(self):
        try:
            lines = self.parse_lit(self.parse_file(self.arguments[0]))
        except OSError as exc:
            document = self.state.document
            return [document.reporter.warning(str(exc), line=self.lineno)]

        node = nodes.container()
        node["classes"] = ["lit-container"]
        node.document = self.state.document

        enum = nodes.enumerated_list()
        enum["classes"] = ["lit-docs"]
        node.append(enum)

        # make first list item
        list_item = nodes.list_item()
        list_item["classes"] = ["lit-item"]

        for is_doc, line in lines:
            if is_doc and line == [""]:
                continue

            section = nodes.section()

            if is_doc:
                section["classes"] = ["lit-annotation"]

                nested_parse_with_titles(self.state, ViewList(line), section)
            else:
                section["classes"] = ["lit-content"]

                code = "\n".join(line)
                literal = nodes.literal_block(code, code)
                literal["language"] = "yaml"
                set_source_info(self, literal)
                section.append(literal)

            list_item.append(section)

            # If we have a pair of annotation/content items, append the list
            # item and create a new list item
            if len(list_item.children) == 2:
                enum.append(list_item)
                list_item = nodes.list_item()
                list_item["classes"] = ["lit-item"]

        # Non-semantic div for styling
        bg = nodes.container()
        bg["classes"] = ["lit-background"]
        node.append(bg)

        return [node]


class LiterateFormula(LiterateCoding):
    """
    Customizations to handle finding and parsing SLS files
    """

    def parse_file(self, sls_path):
        """
        Given a typical Salt SLS path (e.g.: apache.vhosts.standard), find the
        file on the file system and parse it
        """
        config = self.state.document.settings.env.config
        formulas_dirs = config.formulas_dirs
        fpath = sls_path.replace(".", "/")

        name_options = (f"{fpath}.sls", os.path.join(fpath, "init.sls"))

        paths = [
            os.path.join(fdir, fname)
            for fname in name_options
            for fdir in formulas_dirs
        ]

        for i in paths:
            try:
                with open(i, "rb") as f:
                    return f.readlines()
            except OSError:
                pass

        raise OSError(f"Could not find sls file '{sls_path}'")


class CurrentFormula(Directive):
    domain = "salt"
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {}

    def run(self):
        env = self.state.document.settings.env
        modname = self.arguments[0].strip()
        if modname == "None":
            env.temp_data["salt:formula"] = None
        else:
            env.temp_data["salt:formula"] = modname
        return []


class Formula(Directive):
    domain = "salt"
    has_content = True
    required_arguments = 1

    def run(self):
        env = self.state.document.settings.env
        formname = self.arguments[0].strip()

        env.temp_data["salt:formula"] = formname

        if "noindex" in self.options:
            return []

        env.domaindata["salt"]["formulas"][formname] = (
            env.docname,
            self.options.get("synopsis", ""),
            self.options.get("platform", ""),
            "deprecated" in self.options,
        )

        targetnode = nodes.target("", "", ids=["module-" + formname], ismod=True)
        self.state.document.note_explicit_target(targetnode)

        indextext = f"{formname}-formula)"
        inode = addnodes.index(
            entries=[("single", indextext, "module-" + formname, "")]
        )

        return [targetnode, inode]


class State(Directive):
    domain = "salt"
    has_content = True
    required_arguments = 1

    def run(self):
        env = self.state.document.settings.env
        statename = self.arguments[0].strip()

        if "noindex" in self.options:
            return []

        targetnode = nodes.target("", "", ids=["module-" + statename], ismod=True)
        self.state.document.note_explicit_target(targetnode)

        formula = env.temp_data.get("salt:formula")

        indextext = f"{statename} ({formula}-formula)"
        inode = addnodes.index(
            entries=[("single", indextext, f"module-{statename}", "")]
        )

        return [targetnode, inode]


class SLSXRefRole(XRefRole):
    pass


class SaltModuleIndex(python_domain.PythonModuleIndex):
    name = "modindex"
    localname = _("Salt Module Index")
    shortname = _("all salt modules")


class SaltDomain(python_domain.PythonDomain):
    name = "salt"
    label = "Salt"
    data_version = 2

    object_types = python_domain.PythonDomain.object_types
    object_types.update({"state": ObjType(_("state"), "state")})

    directives = python_domain.PythonDomain.directives
    directives.update(
        {
            "event": Event,
            "state": State,
            "formula": LiterateFormula,
            "currentformula": CurrentFormula,
            "saltconfig": LiterateCoding,
        }
    )

    roles = python_domain.PythonDomain.roles
    roles.update({"formula": SLSXRefRole()})

    initial_data = python_domain.PythonDomain.initial_data
    initial_data.update({"formulas": {}})

    indices = [
        SaltModuleIndex,
    ]

    def resolve_xref(self, env, fromdocname, builder, type, target, node, contnode):
        if type == "formula" and target in self.data["formulas"]:
            doc, _, _, _ = self.data["formulas"].get(target, (None, None))
            if doc:
                return make_refnode(builder, fromdocname, doc, target, contnode, target)
        else:
            super().resolve_xref(
                env, fromdocname, builder, type, target, node, contnode
            )


# Monkey-patch the Python domain remove the python module index
python_domain.PythonDomain.indices = [SaltModuleIndex]


def setup(app):
    app.add_domain(SaltDomain)

    formulas_path = "templates/formulas"
    formulas_dir = os.path.join(
        os.path.abspath(os.path.dirname(salt.__file__)), formulas_path
    )
    app.add_config_value("formulas_dirs", [formulas_dir], "env")

    app.add_crossref_type(
        directivename="conf_master",
        rolename="conf_master",
        indextemplate="pair: %s; conf/master",
    )
    app.add_crossref_type(
        directivename="conf_minion",
        rolename="conf_minion",
        indextemplate="pair: %s; conf/minion",
    )
    app.add_crossref_type(
        directivename="conf_proxy",
        rolename="conf_proxy",
        indextemplate="pair: %s; conf/proxy",
    )
    app.add_crossref_type(
        directivename="conf_log",
        rolename="conf_log",
        indextemplate="pair: %s; conf/logging",
    )
    app.add_crossref_type(
        directivename="jinja_ref",
        rolename="jinja_ref",
        indextemplate="pair: %s; jinja filters",
    )
    return dict(parallel_read_safe=True, parallel_write_safe=True)

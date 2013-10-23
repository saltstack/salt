from docutils import nodes

from sphinx import addnodes
from sphinx.directives import ObjectDescription, Directive
from sphinx.domains import Domain, ObjType
from sphinx.locale import l_, _
from sphinx.roles import XRefRole
from sphinx.util.nodes import make_refnode

from sphinx.domains import python as python_domain

class CurrentFormula(Directive):
    domain = 'salt'
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {}

    def run(self):
        env = self.state.document.settings.env
        modname = self.arguments[0].strip()
        if modname == 'None':
            env.temp_data['salt:formula'] = None
        else:
            env.temp_data['salt:formula'] = modname
        return []


class Formula(Directive):
    domain = 'salt'
    has_content = True
    required_arguments = 1

    def run(self):
        env = self.state.document.settings.env
        formname = self.arguments[0].strip()

        env.temp_data['salt:formula'] = formname

        if 'noindex' in self.options:
            return []

        env.domaindata['salt']['formulas'][formname] = (
                env.docname,
                self.options.get('synopsis', ''),
                self.options.get('platform', ''),
                'deprecated' in self.options)

        targetnode = nodes.target('', '', ids=['module-' + formname],
                ismod=True)
        self.state.document.note_explicit_target(targetnode)

        indextext = u'{0}-formula)'.format(formname)
        inode = addnodes.index(entries=[('single', indextext,
                                         'module-' + formname, '')])

        return [targetnode, inode]


class State(Directive):
    domain = 'salt'
    has_content = True
    required_arguments = 1

    def run(self):
        env = self.state.document.settings.env
        statename = self.arguments[0].strip()

        if 'noindex' in self.options:
            return []

        targetnode = nodes.target('', '', ids=['module-' + statename],
                ismod=True)
        self.state.document.note_explicit_target(targetnode)

        formula = env.temp_data.get('salt:formula')

        indextext = u'{1} ({0}-formula)'.format(formula, statename)
        inode = addnodes.index(entries=[
            ('single', indextext, 'module-{0}'.format(statename), ''),
        ])

        return [targetnode, inode]


class SLSXRefRole(XRefRole):
    pass


class SaltModuleIndex(python_domain.PythonModuleIndex):
    name = 'modindex'
    localname = l_('Salt Module Index')
    shortname = l_('all salt modules')


class SaltDomain(python_domain.PythonDomain):
    name = 'salt'
    label = 'Salt'
    data_version = 2

    object_types = python_domain.PythonDomain.object_types
    object_types.update({
        'state': ObjType(l_('state'), 'state'),
    })

    directives = python_domain.PythonDomain.directives
    directives.update({
        'state': State,
        'formula': Formula,
        'currentformula': CurrentFormula,
    })

    roles = python_domain.PythonDomain.roles
    roles.update({
        'formula': SLSXRefRole(),
    })

    initial_data = python_domain.PythonDomain.initial_data
    initial_data.update({
        'formulas': {},
    })

    indices = [
        SaltModuleIndex,
    ]

    def resolve_xref(self, env, fromdocname, builder, type, target, node,
            contnode):
        if type == 'formula' and target in self.data['formulas']:
            doc, _, _, _ = self.data['formulas'].get(target, (None, None))
            if doc:
                return make_refnode(builder, fromdocname, doc, target,
                        contnode, target)
        else:
            super(SaltDomain, self).resolve_xref(env, fromdocname, builder,
                    type, target, node, contnode)

# Monkey-patch the Python domain remove the python module index
python_domain.PythonDomain.indices = []


def setup(app):
    app.add_domain(SaltDomain)

    app.add_crossref_type(directivename="conf_master", rolename="conf_master",
            indextemplate="pair: %s; conf/master")
    app.add_crossref_type(directivename="conf_minion", rolename="conf_minion",
            indextemplate="pair: %s; conf/minion")
    app.add_crossref_type(directivename="conf_log", rolename="conf_log",
            indextemplate="pair: %s; conf/logging")

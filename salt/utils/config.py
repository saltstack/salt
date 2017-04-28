# -*- coding: utf-8 -*-
'''
    salt.utils.config
    ~~~~~~~~~~~~~~~~~

    Configuration generation

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

import re
import inspect
import textwrap
import docutils.nodes
import docutils.utils
import docutils.frontend
import docutils.parsers.rst

# inspect.getdoc
# http://repo.or.cz/w/docutils.git/blob/HEAD:/docutils/docutils/parsers/rst/__init__.py


DEFAULT = object

def _camelcase_joined(s, union=' '):
    return re.sub(
        r'(^|[a-z])([A-Z])',
        lambda m: union.join(
            [i for i in m.groups() if i]
        ), s
    )


class DocGenMixIn(object):

    _pretty_name = None

    def __new__(cls, *args):
        instance = object.__new__(cls)
        instance.__original_doc__ = cls.__doc__
        return instance

    def __getattribute__(self, name):
        if name == '__doc__':
            return object.__getattribute__(self, '__docgen__')(
                object.__getattribute__(self, name)
            )
        return object.__getattribute__(self, name)

    @property
    def pretty_name(self):
        if self._pretty_name is None:
            self._pretty_name = _camelcase_joined(self.__class__.__name__)
        return self._pretty_name

    def to_yaml(self):
        if not hasattr(self, '_rst_parser'):
            self._rst_parser = docutils.parsers.rst.Parser()
            self._rst_settings = docutils.frontend.OptionParser(
                components=(docutils.parsers.rst.Parser,)
            ).get_default_values()
            self._rst_document = docutils.utils.new_document(
                '{0}.__doc__'.format(self.__class__.__name__),
                self._rst_settings
            )
            self._rst_parser.parse(
                inspect.cleandoc(self.__doc__),
                self._rst_document
            )

        visitor = DocutilsYamlTranslator(self._rst_document, self)
        self._rst_document.walkabout(visitor)

        output = ''.join(visitor.output)

        return output


class Configuration(DocGenMixIn):

    def __init__(self, *entries):
        self.__entries = entries or []

    def add_entry(self, entry):
        self.__entries.append(entry)

    def __iter__(self):
        for entry in self.__entries:
            yield entry

    def flatten(self):
        '''
        Return the name/value as a dictionary
        '''
        out = {}
        for entry in self:
            out.update(entry.flatten())
        return out

    @property
    def value(self):
        for entry in self:
            yield entry.flatten()
        raise StopIteration

    def __docgen__(self, original_doc):
        doc = u'{1}\n{0}\n{1}\n\n'.format(
            self.pretty_name,
            (u'=' * len(self.pretty_name))
        )
        doc += inspect.cleandoc(original_doc)
        for entry in self:
            doc += u'\n\n\n' + entry.__doc__
        return doc


class ConfigSection(Configuration):
    _pretty_name = None

    def __docgen__(self, original_doc):
        doc = u'{1}\n{0}\n{1}\n\n'.format(
            self.pretty_name, (u'~' * len(self.pretty_name))
        )
        doc += inspect.cleandoc(original_doc)
        for entry in self:
            doc += '\n\n\n' + entry.__doc__
        return doc


class ConfigEntry(DocGenMixIn):
    _name = _pretty_name = None
    _value = None
    default = DEFAULT

    def __init__(self, value=None):
        self._value = value

    @property
    def name(self):
        if self._name is None:
            return _camelcase_joined(self.__class__.__name__.lower(), '_')
        return self._name

    @property
    def value(self):
        if self._value is not None:
            return self._value
        return self.default

    def flatten(self):
        '''
        Return the name/value as a dictionary
        '''
        return {
            self.name: self.value
        }

    def __docgen__(self, original_doc):
        doc = u'{1}\n{0}\n{1}\n\n'.format(
            self.pretty_name,
            (u'-' * len(self.pretty_name))
        )
        doc += inspect.cleandoc(original_doc)

        if self.default is not DEFAULT:
            doc += u'\n\n:Default: ``{0!r}``'.format(self.default)

        #doc += u'\n\n.. {0}{1}: {2!r}'.format(
        #    self._value is None and '#' or '', self.name, self.value
        #)
        return doc


class DocutilsYamlTranslator(docutils.nodes.GenericNodeVisitor):

    supported = ('yaml',)

    def __init__(self, document, instance):
        docutils.nodes.GenericNodeVisitor.__init__(self, document)
        self.instance = instance

        # Reporter
        self.warn = self.document.reporter.warning
        self.error = self.document.reporter.error

        # Settings
        #self.settings = settings = document.settings
        #self.indent = self.newline = ''
        #if settings.newlines:
        #    self.newline = '\n'
        #if settings.indents:
        self.newline = '\n'
        self.indent = '  '
        self.level = 0  # indentation level
        self.in_simple = 0  # level of nesting inside mixed-content elements
        self.in_section = 0
        self.in_field_list = 0
        self.has_sub_section = False

        # Output
        self.output = []

    # generic visit and depart methods
    def default_visit(self, node):
        print 1, node
        return

    def default_departure(self, node):
        print 2, node
        return

    def visit_paragraph(self, node):
        pass

    def depart_paragraph(self, node):
        if not self.in_simple:
            return
        #self.output.append('\n')

    def visit_title(self, node):
        self.output.append(self.newline)
        self.in_simple += 1
        if self.in_section <= 1:
            # Consider this html's h1
            self.output.append(
                u'{0:#^{width}}'.format(
                    '  {0}  '.format(node.astext()),
                    width=80
                )
            )
        elif self.in_section == 2:
            if self.has_sub_section:
                # Consider this h2
                self.output.append(
                    u'# {0:*^{width}}'.format(
                        '  {0}  '.format(node.astext()),
                        width=78
                    )
                )
            else:
                self.output.append(
                    '# {0}'.format(node.astext())
                )
        elif self.in_section > 2:
            # Consider this h3 and above
            self.output.append(
                '# {0}'.format(node.astext())
            )
        self.output.append(self.newline)

    def depart_title(self, node):
        #print 1111111111, node,
        #print node.attlist(), node.attributes,
        #print dir(node)
        if self.in_section <= 1:
            # Consider this html's h1
            self.output.append('#' * 80)
        elif self.in_section == 2:
            # Consider this h2
            if self.has_sub_section:
                #print 2222222222, node, self.has_sub_section
                self.output.append('# {0}'.format('*' * 78))
            else:
                self.output.append('# {0}'.format('-' * len(node.astext())))
            #self.output.append('# {0}'.format('~' * 78))
        elif self.in_section > 2:
            # Consider this h3 and above
            self.output.append('# {0}'.format('-' * len(node.astext())))

        self.output.append('\n#\n')
        self.in_simple -= 1

    def visit_literal_block(self, node):
        if self.in_field_list:
            return

        self.in_simple += 1
        self.output.append('#\n# Example:\n')
        self.level += 1
        for line in node.astext().splitlines():
            self.output.append(
                '# {0}{1}'.format(self.indent * self.level, line)
            )
        self.level -= 1

    def depart_literal_block(self, node):
        if self.in_field_list:
            return
        self.output.append('\n')
        self.in_simple -= 1

    def visit_Text(self, node):
        if not self.in_simple:
            lines = textwrap.wrap(node.astext(), 78)
            while lines:
                self.output.append('# {0}'.format(lines.pop(0)))
                if not lines:
                    break
                self.output.append(self.newline)

    def depart_Text(self, node):
        if not self.in_simple:
            self.output.append('\n')

    def visit_section(self, node):
        self.in_section += 1
        self.has_sub_section = [
            c for c in node.children if c.tagname == 'section'
        ]
        print 123, node, self.has_sub_section
        #self.output.append(self.newline)

    def depart_section(self, node):
        self.output.append(self.newline)
        if self.has_sub_section:
            self.has_sub_section = False
        self.in_section -= 1

    def visit_field_list(self, node):
        self.in_field_list += 1

    def depart_field_list(self, node):
        self.in_field_list -= 1

    def visit_field_name(self, node):
        self.in_simple += 1

    def depart_field_name(self, node):
        self.in_simple -= 1

    def visit_field_body(self, node):
        self.in_simple += 1

    def depart_field_body(self, node):
        self.in_simple -= 1

    def visit_field(self, node):
        name, body = node.children
        self.output.append(
            '#\n# {0}: {1}'.format(
                name.astext(), body.astext()
            )
        )

    def depart_field(self, node):
        self.output.append(self.newline)

    def visit_comment(self, node):
        self.in_simple += 1
        self.output.append(node.astext())

    def depart_comment(self, node):
        self.in_simple -= 1
        self.output.append(self.newline)


class Interface(ConfigEntry):
    '''
    The local interface to bind to.

    .. code-block:: yaml

        interface: 192.168.0.1
    '''

    default = '0.0.0.0'


class User(ConfigEntry):
    '''

    The user to run the Salt processes

    .. code-block:: yaml

        user: root
    '''

    default = 'root'


class DefaultInclude(ConfigEntry):
    '''
    Per default the master will automatically include all config files
    from master.d/\*.conf (master.d is a directory in the same directory
    as the main master config file)
    '''

    _name = 'default_include'
    default = 'master.d/*.conf'


class MasterModuleManagement(ConfigSection):
    '''
    Manage how master side modules are loaded
    '''


class RunnerDirs(ConfigEntry):
    '''
    Add any additional locations to look for master runners
    '''
    _name = 'runner_dirs'
    default = []


class EnableCythonFoo(ConfigEntry):
    '''
    Enable Cython for master side modules
    '''
    _name = 'cython_enable'
    default = False


class MainConf(Configuration):
    '''
    This configuration file is used to manage the behavior of the Salt Master.
    Values that are commented out but have no space after the comment are
    defaults that need not be set in the config. If there is a space after the
    comment that the value is presented as an example and is not the default.
    '''

    _pretty_name = 'Primary configuration settings'


def main():

    #print inspect.cleandoc(User2().__doc__)
    #print 123, '\n', User().__doc__, '\n', 123
    #print User().to_yaml()
    #return

    #print Interface().__doc__
    #print Interface().to_yaml()
    #print
    #print Interface('127.0.0.1').__doc__
    #print Interface('127.0.0.1').to_yaml()
    #print
    #return


    c = MainConf(
        User(),
        Interface('127.0.0.1'),
        DefaultInclude(),
        MasterModuleManagement(
            RunnerDirs(),
            EnableCythonFoo()
        )
    )

    print c.__doc__
    #return
    print c.flatten()

    #print c.to_yaml()
    print c.to_yaml()

if __name__ == '__main__':
    main()

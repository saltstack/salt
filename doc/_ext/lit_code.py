# coding: utf-8
'''
A literate-style code block
'''
import itertools
import os
import re

from docutils import nodes
from docutils.parsers.rst import Directive

from sphinx.util.nodes import nested_parse_with_titles
from sphinx.util.nodes import set_source_info
from docutils.statemachine import ViewList

import salt

def parse_lit(lines):
    '''
    Parse a string line-by-line delineating comments and code

    :returns: An tuple of boolean/list-of-string pairs. True designates a
        comment; False designates code.
    '''
    comment_char = '#'
    comment = re.compile(r'^\s*{0}[ \n]'.format(comment_char))
    section_test = lambda val: bool(comment.match(val))

    sections = []
    for is_doc, group in itertools.groupby(lines, section_test):
        if is_doc:
            text = [comment.sub('', i).rstrip('\r\n') for i in group]
        else:
            text = [i.rstrip('\r\n') for i in group]

        sections.append((is_doc, text))

    return sections

def parse_sls_file(config, sls_path):
    '''
    Given a typical Salt SLS path (e.g.: apache.vhosts.standard), find the file
    on the file system and parse it
    '''
    formulas_dirs = config.formulas_dirs
    fpath = sls_path.replace('.', '/')

    name_options = (
        '{0}.sls'.format(fpath),
        os.path.join(fpath, 'init.sls')
    )

    paths = [os.path.join(fdir, fname)
            for fname in name_options
                for fdir in formulas_dirs]

    for i in paths:
        try:
            with open(i, 'rb') as f:
                return parse_lit(f)
        except IOError:
            pass

    raise Exception("Could not find sls file '{0}'".format(sls_path))

class LiterateCoding(Directive):
    '''
    Auto-doc SLS files using literate-style comment/code separation
    '''
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False

    def run(self):
        config = self.state.document.settings.env.config
        lines = parse_sls_file(config, self.arguments[0])

        node = nodes.section()
        node.document = self.state.document
        enum = nodes.enumerated_list()
        enum['classes'] = ['lit-docs']
        node.append(enum)

        # make first list item
        list_item = nodes.list_item()
        list_item['classes'] = ['lit-item']

        for is_doc, line in lines:
            if is_doc and line == ['']:
                continue

            section = nodes.section()

            if is_doc:
                section['classes'] = ['lit-annotation']

                nested_parse_with_titles(self.state, ViewList(line), section)
            else:
                section['classes'] = ['lit-content']

                code = '\n'.join(line)
                literal = nodes.literal_block(code, code)
                literal['language'] = 'yaml'
                set_source_info(self, literal)
                section.append(literal)

            list_item.append(section)

            # If we have a pair of annotation/content items, append the list
            # item and create a new list item
            if len(list_item.children) == 2:
                enum.append(list_item)
                list_item = nodes.list_item()
                list_item['classes'] = ['lit-item']

        return node.children

def setup(app):
    '''
    Register the above directive with Sphinx
    '''
    formulas_path = 'templates/formulas'
    formulas_dir = os.path.join(os.path.abspath(os.path.dirname(salt.__file__)),
            formulas_path)

    app.add_config_value('formulas_dirs', [formulas_dir], 'env')
    app.add_directive('formula', LiterateCoding)

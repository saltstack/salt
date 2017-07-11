from __future__ import print_function

import os
import re
import argparse
import imp
import inspect


import salt.states
import salt.modules


def main():
    args = get_args()
    
    if args.load_whitelist:
        whitelist = load_whitelist(args.load_whitelist)

    modules = get_modules()
    search_keywords = set(['file', 'directory', 'path', 'location'])
    for module in modules:
        # module_path = get_path_to_module(module.__name__)
        # zookeeper, # import after __virtualname__

        start_line_to_function = {}
        for function in get_global_functions(module):
            function_parameters = []
            for parameter, docs in get_function_parameter_docs(function):
                parameter_id = '%s.%s:%s' % ('.'.join(module.__name__.split('.')[1:]),
                    function.__name__, parameter)
                if args.load_whitelist:
                    if parameter_id in whitelist:
                        function_parameters.append(parameter)
                else:
                    doc_words = set(word.lower() for word in docs.split())
                    # super inefficient search, whatever
                    for search_keyword in search_keywords:
                        if search_keyword in doc_words:
                            print('%s \t%s' % (parameter_id, docs))
                            break

            if function_parameters:
                try:
                    start_line_to_function[find_function_first_line(function)] = (function, function_parameters)
                except IOError:
                    print('Failed to find source code for %s.%s, probably decorated' % (
                        function.__module__, function.__name__))

        for line_number, (function, function_parameters) in sorted(start_line_to_function.items(), reverse=True):
            add_expanduser_call(function, function_parameters, line_number)

        if start_line_to_function:
            add_import_statement(module)


def add_import_statement(module):
    module_path = get_path_to_module(module.__name__)
    has_import = False
    header_lines = []
    # Modules should have a section, that follows python libs and is proceeded by 3rd party libs
    # # Import salt libs
    # import salt.utils

    # Can look for anything `import salt.*` or `from salt.*`, if so add in that section
    # If no such section, add it after the first unbroken string of `import *`, unless it's prepended with `# Import 3*`
    header_done = False
    body_lines = []
    with open(module_path, 'r+') as fh:
        for line in fh:
            if line.startswith('def '):
                header_done = True
            if header_done:
                body_lines.append(line.rstrip())
            else:
                header_lines.append(line.rstrip())

    # Check it it's already present
    for line in header_lines:
        if line == 'import salt.utils':
            return

    # Check if we have a salt import section
    salt_imports = []
    salt_imports_location = -1

    ideal_import_location = -1 # used to track in case there's no imports, should be right after the docs
    in_docs = False
    for line_number, line in enumerate(header_lines):
        if line == "'''":
            if not in_docs:
                in_docs = True
            else:
                ideal_import_location = line_number + 2

        if salt_imports and not line:
            break
        if '3rd-party' in line:
            # Found 3rd party section, no salt imports
            ideal_import_location = line_number
            break
        if line.startswith('import salt.') or line.startswith('from salt.'):
            if salt_imports_location == -1:
                salt_imports_location = line_number
            salt_imports.append(line)

        if line.startswith('import ') or line.startswith('from '):
            # Assumed to be normal python stdlib import
            ideal_import_location = line_number + 1

    if salt_imports:
        print('adding import to %s with existing salt imports' % module_path)
        salt_imports.append('import salt.utils')
        def line_sorter(line):
            import_type, rest_of_import = line.split(' ', 1)
            return (0 if import_type == 'import' else 1, rest_of_import)
        salt_imports.sort(key=line_sorter)
        header_lines[salt_imports_location:salt_imports_location + len(salt_imports) - 1] = salt_imports
        # Not the exact line inserted, but the only thing that counts here is
        # that it's in the import section at all
        write_header_and_body(module_path, header_lines, body_lines)
        return

    header_lines.insert(ideal_import_location, '# Import Salt Libs')
    header_lines.insert(ideal_import_location + 1, 'import salt.utils')
    if header_lines[ideal_import_location + 2] != '':
        # if next line after import is not blank, add a blank
        header_lines.insert(ideal_import_location + 2, '')
    if header_lines[ideal_import_location - 1] != '':
        # If last line before import location is not blank, add a blank
        header_lines.insert(ideal_import_location, '')

    write_header_and_body(module_path, header_lines, body_lines)


def write_header_and_body(module_path, header_lines, body_lines):
    with open(module_path, 'w') as fh:
        for line in header_lines + body_lines:
            fh.write(line)
            fh.write('\n')


def get_path_to_module(module_name):
    return os.path.join(module_name.replace('.', '/') + '.py')


def get_args():
    # By default we only write all the candidate parameters to stdout, to do
    # the fix you need to filter that list for false positives, and pass a flag
    # with the edited list
    parser = argparse.ArgumentParser()
    parser.add_argument('-L', '--load-whitelist')
    return parser.parse_args()


def add_expanduser_call(function, parameters, line_number):
    function_source_file = get_path_to_module(function.__module__)
    with open(function_source_file, 'r+') as fh:
        source_file_lines = fh.readlines()
        source_file_lines.insert(line_number, '    {0} = salt.utils.expanduser({0})\n'.format(
            ', '.join(parameters)))
        fh.seek(0)
        for line in source_file_lines:
            fh.write(line)


def find_function_first_line(function):
    ''' return value is 0-indexed'''
    sourcelines, line_number = inspect.getsourcelines(function)
    doc_end_marker_re = re.compile(r'^    r?(?:\'\'\'|\"\"\")\n$')
    found_doc_markers = 0
    for line_offset, line in enumerate(sourcelines):
        if doc_end_marker_re.match(line):
            found_doc_markers += 1
            if found_doc_markers == 2:
                line_number += line_offset
                break
    else:
        for line in sourcelines:
            print(line, end='')
        # import pdb; pdb.set_trace()
        raise ValueError("Didn't find end marker for %s.%s" % (function.__module__,
            function.__name__))
    return line_number


def load_whitelist(whitelist_path):
    # The whitelist should hold module:parameter pairs, then optionally the documentation for the parameter
    # We filter by a regex to enable commenting out lines, adding whitespace, etc
    whitelist = set()
    valid_line_re = re.compile(r'^((?:modules|states)\.\w+\.\w+:\w+).*')
    with open(whitelist_path) as fh:
        for line in fh:
            valid_match = valid_line_re.match(line)
            if not valid_match:
                continue
            parameter_id = valid_match.group(1)
            whitelist.add(parameter_id)
    return whitelist


def get_modules():
    valid_python_re = re.compile(r'^\w+\.py$')
    for filename in os.listdir('salt/states'):
        if not valid_python_re.match(filename):
            continue
        module_name = os.path.splitext(filename)[0]
        module = imp.find_module(module_name, salt.states.__path__)
        yield imp.load_module('salt.states.%s' % module_name, *module)

    for filename in os.listdir('salt/modules'):
        if not valid_python_re.match(filename):
            continue
        module_name = os.path.splitext(filename)[0]
        module = imp.find_module(module_name, salt.modules.__path__)
        yield imp.load_module('salt.modules.%s' % module_name, *module)


def get_global_functions(module):
    for global_name in dir(module):
        if global_name.startswith('_'):
            continue
        
        function = getattr(module, global_name)

        if not inspect.isfunction(function):
            continue

        yield function    


def get_function_parameter_docs(function):
    # TODO: Also needs to extract ':param <parameter>: \n?<docs>'
    parameter_names = get_function_parameter_names(function)
    if not function.__doc__:
        return
    doc_lines = function.__doc__.split('\n')

    # Search for docs like
    # param
    #     docs
    i = 0
    while i < len(doc_lines):
        line = doc_lines[i]
        parameter_name = line.strip()
        if parameter_name in parameter_names:
            parameter_doc = []
            while doc_lines[i+1].startswith(' '*8):
                parameter_doc.append(doc_lines[i+1].strip())
                i += 1
            yield parameter_name, ''.join(parameter_doc)
        i += 1

    # Search for docs like
    # :param param: docs
    doc_re = re.compile(r':param (\w+):([\w\s\n.,/]+)', re.MULTILINE)
    for parameter_name, parameter_doc in doc_re.findall(function.__doc__):
        clean_docs = ' '.join(parameter_doc.split())
        yield parameter_name, clean_docs


def get_function_parameter_names(function):
    argspec = inspect.getargspec(function)
    parameter_names = set(argspec.args)

    # To avoid some false positives, remove parameters with default arguments
    # that are not None or string
    for parameter, default in zip(reversed(argspec.args), reversed(argspec.defaults or [])):
        if type(default) not in (type(None), type('')):
            parameter_names.remove(parameter)

    return parameter_names


if __name__ == '__main__':
    main()

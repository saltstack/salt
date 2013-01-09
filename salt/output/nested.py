'''
Recursively display netsted data
'''

# Import salt libs
import salt.utils

class NestDisplay(object):
    '''
    '''
    def __init__(self):
        self.colors = salt.utils.get_colors(__opts__.get('color'))

    def display(self, ret, indent, prefix, out):
        '''
        Recursively interate down through data structures to determine output
        '''
        if ret is None or ret is True or ret is False:
            out += '{0}{1}{2}{3}{4}\n'.format(
                    self.colors['YELLOW'],
                    ' ' * indent,
                    prefix,
                    ret,
                    self.colors['ENDC'])
        elif isinstance(ret, int):
            out += '{0}{1}{2}{3}{4}\n'.format(
                    self.colors['YELLOW'],
                    ' ' * indent,
                    prefix,
                    ret,
                    self.colors['ENDC'])
        elif isinstance(ret, str):
            lines = ret.split('\n')
            for line in lines:
                out += '{0}{1}{2}{3}{4}\n'.format(
                        self.colors['GREEN'],
                        ' ' * indent,
                        prefix,
                        line,
                        self.colors['ENDC'])
        elif isinstance(ret, list) or isinstance(ret, tuple):
            for ind in ret:
                out = self.display(ind, indent, '- ', out)
        elif isinstance(ret, dict):
            for key, val in ret.items():
                out += '{0}{1}{2}{3}{4}:\n'.format(
                        self.colors['CYAN'],
                        ' ' * indent,
                        prefix,
                        key,
                        self.colors['ENDC'])
                out = self.display(val, indent + 4, '', out)
        return out

def output(ret):
    '''
    Display ret data
    '''
    nest = NestDisplay()
    return nest.display(ret, 0, '', '')

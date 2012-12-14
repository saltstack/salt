'''
Special outputter for grains
'''

# Import salt libs
import salt.utils


def output(grains):
    '''
    Output the grains in a clean way
    '''
    colors = salt.utils.get_colors(__opts__.get('color'))
    ret = ''
    for id_, minion in grains.items():
        ret += '{0}{1}{2}:\n'.format(colors['GREEN'], id_, colors['ENDC'])
        for key in sorted(minion):
            ret += '  {0}{1}{2}:'.format(colors['CYAN'], key, colors['ENDC'])
            if key == 'cpu_flags':
                ret += colors['LIGHT_GREEN']
                for val in minion[key]:
                    ret += ' {0}'.format(val)
                ret += '{0}\n'.format(colors['ENDC'])
            elif key == 'pythonversion':
                ret += ' {0}'.format(colors['LIGHT_GREEN'])
                for val in minion[key]:
                    ret += '{0}.'.format(str(val))
                ret = ret[:-1]
                ret += '{0}\n'.format(colors['ENDC'])
            elif isinstance(minion[key], list):
                for val in minion[key]:
                    ret += '\n      {0}{1}{2}'.format(colors['LIGHT_GREEN'], val, colors['ENDC'])
                ret += '\n'
            else:
                ret += ' {0}{1}{2}\n'.format(colors['LIGHT_GREEN'], minion[key], colors['ENDC'])
    return ret


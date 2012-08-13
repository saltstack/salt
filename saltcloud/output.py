'''
Print out data in a clean and structured way specific to the data being
printed
'''

# Import Salt libs
import salt.utils

def double_layer(data, color=True):
    '''
    Print out double layered dict returns (like from list-images and
    list-sizes)
    '''
    colors = salt.utils.get_colors(color)
    for top_key in sorted(data):
        print('{0}{1}{2}'.format(colors['GREEN'], top_key, colors['ENDC']))
        for sec_key in sorted(data[top_key]):
            print('  {0}{1}{2}'.format(
                colors['YELLOW'],
                sec_key,
                colors['ENDC']))
            tval = data[top_key][sec_key]
            for fkey in sorted(tval):
                val = data[top_key][sec_key][fkey]
                if isinstance(val, str) or isinstance(val, int):
                    print('    {0}{1}: {2}{3}'.format(
                        colors['LIGHT_GREEN'],
                        fkey,
                        data[top_key][sec_key][fkey],
                        colors['ENDC']))
                if isinstance(val, dict):
                    print('    {0}{1}:{2}'.format(
                        colors['LIGHT_GREEN'],
                        fkey,
                        colors['ENDC']))
                    for ekey in sorted(val):
                        print('      {0}{1}: {2}{3}'.format(
                            colors['LIGHT_GREEN'],
                            ekey,
                            val[ekey],
                            colors['ENDC']))

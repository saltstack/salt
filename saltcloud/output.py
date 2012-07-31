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
                colors['DARK_GRAY'],
                sec_key,
                colors['ENDC']))
            for fkey in sorted(data[top_key][sec_key]):
                print('    {0}{1}: {2}{3}'.format(
                    colors['CYAN'],
                    fkey,
                    data[top_key][sec_key][fkey],
                    colors['ENDC']))

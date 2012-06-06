'''
These grains provide additional information about the network interfaces.
'''

# Define __salt__ so the call to network.interfaces works
import salt.modules.network
__salt__ = {'network.interfaces': salt.modules.network.interfaces}


def subnets():
    '''
    Returns a list of all subnets to which the host belongs
    '''
    # Provides:
    #   subnets
    def dotted_quad_to_binary(dotted_quad):
        binary_str = ''
        for octet in dotted_quad.split('.'):
            # Convert the decimal octet to binary and pad with trailing zeroes
            # if necessary.
            binary_str += str(bin(int(octet)))[2:].zfill(8)
        return eval('0b' + binary_str)

    def binary_to_dotted_quad(binary):
        # Get string representation, sans the leading '0b'.
        s = str(bin(binary))[2:]
        # Split each 8 chars into separate strings, representing the decimal
        # versions of each octet.
        quad = [str(eval('0b' + s[i:i+8])) for i in range(0,len(s),8)]
        return '.'.join(quad)

    subnets = []
    ifaces = __salt__['network.interfaces']()
    for ipaddr,netmask in [(ifaces[z].get('ipaddr'),ifaces[z].get('netmask'))
                            for z in ifaces.keys()]:
        # If either the ip or netmask wasn't present, something is wrong. Skip
        # this interface and move to the next. Might also want to log something
        # here.
        if ipaddr is None or netmask is None: continue

        # Skip any loopback interfaces
        if ipaddr == '127.0.0.1': continue

        ipaddr_bin = dotted_quad_to_binary(ipaddr)
        netmask_bin = dotted_quad_to_binary(netmask)

        # Perform logical AND on the ip and netmask, and convert the result
        # back into a dotted quad.
        net_start = binary_to_dotted_quad(ipaddr_bin & netmask_bin)

        # Get CIDR notation
        netmask_bin_str = str(bin(netmask_bin))[2:]
        cidr = str(len(netmask_bin_str.rstrip('0')))

        subnets.append(net_start + '/' + cidr)

    return {'subnets': subnets}



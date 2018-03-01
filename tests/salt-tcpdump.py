#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Author: Volker Schwicking, vs@heg.com

Salt tcpdumper to visualize whats happening network-wise on
the salt-master. It uses pcapy and inspects all incoming networks
packets and filters only the ones relevant to salt-communication.

based on: http://oss.coresecurity.com/projects/pcapy.html

$ salt-tcpdump.py -n 2

Will print the overall tcp-status of tcp-connections to salts
default ports in a two second interval.


$ salt-tcpdump.py -I -n 2

Will print the number of IPs making new connections to salts
default ports.


$ salt-tcpdump.py -I -n 2 -i eth1

Same as before but on eth1 instead of the default eth0.

Rough equivalents to this script could be:

For Port 4505
tcpdump "tcp[tcpflags] & tcp-syn != 0" and port 4505 and "tcp[tcpflags] & tcp-ack == 0"

For Port 4506
tcpdump "tcp[tcpflags] & tcp-syn != 0" and port 4506 and "tcp[tcpflags] & tcp-ack == 0"
'''
# pylint: disable=resource-leakage
# Import Python Libs
from __future__ import absolute_import, print_function
import socket
from struct import unpack
import pcapy  # pylint: disable=import-error,3rd-party-module-not-gated
import sys
import argparse  # pylint: disable=minimum-python-version
import time


class ArgParser(object):
    '''
    Simple Argument-Parser class
    '''
    def __init__(self):
        '''
        Init the Parser
        '''
        self.main_parser = argparse.ArgumentParser()
        self.add_args()

    def add_args(self):
        '''
        Add new arguments
        '''

        self.main_parser.add_argument('-i',
                                      type=str,
                                      default='eth0',
                                      dest='iface',
                                      required=False,
                                      help=('the interface to dump the'
                                            'master runs on(default:eth0)'))

        self.main_parser.add_argument('-n',
                                      type=int,
                                      default=5,
                                      dest='ival',
                                      required=False,
                                      help=('interval for printing stats '
                                            '(default:5)'))

        self.main_parser.add_argument('-I',
                                      type=bool,
                                      default=False,
                                      const=True,
                                      nargs='?',
                                      dest='only_ip',
                                      required=False,
                                      help=('print unique IPs making new '
                                            'connections with SYN set'))

    def parse_args(self):
        '''
        parses and returns the given arguments in a namespace object
        '''
        return self.main_parser.parse_args()


class PCAPParser(object):
    '''
    parses a network packet on given device and
    returns source, target, source_port and dest_port
    '''

    def __init__(self, iface):
        self.iface = iface

    def run(self):
        '''
        main loop for the packet-parser
        '''
        # open device
        # Arguments here are:
        #   device
        #   snaplen (maximum number of bytes to capture _per_packet_)
        #   promiscious mode (1 for true)
        #   timeout (in milliseconds)
        cap = pcapy.open_live(self.iface, 65536, 1, 0)

        count = 0
        l_time = None

        while 1:

            packet_data = {
                           'ip': {},
                           'tcp': {}
                          }

            (header, packet) = cap.next()  # pylint: disable=incompatible-py3-code

            eth_length, eth_protocol = self.parse_ether(packet)

            # Parse IP packets, IP Protocol number = 8
            if eth_protocol == 8:
                # Parse IP header
                # take first 20 characters for the ip header
                version_ihl, version, ihl, iph_length, ttl, protocol, s_addr, d_addr = self.parse_ip(packet, eth_length)
                packet_data['ip']['s_addr'] = s_addr
                packet_data['ip']['d_addr'] = d_addr

                # TCP protocol
                if protocol == 6:

                    source_port, dest_port, flags, data = self.parse_tcp(packet, iph_length, eth_length)
                    packet_data['tcp']['d_port'] = dest_port
                    packet_data['tcp']['s_port'] = source_port
                    packet_data['tcp']['flags'] = flags
                    packet_data['tcp']['data'] = data
                    yield packet_data

    def parse_ether(self, packet):
        '''
        parse ethernet_header and return size and protocol
        '''
        eth_length = 14

        eth_header = packet[:eth_length]
        eth = unpack('!6s6sH', eth_header)
        eth_protocol = socket.ntohs(eth[2])
        return eth_length, eth_protocol

    def parse_ip(self, packet, eth_length):
        '''
        parse ip_header and return all ip data fields
        '''
        # Parse IP header
        # take first 20 characters for the ip header
        ip_header = packet[eth_length:20+eth_length]

        # now unpack them:)
        iph = unpack('!BBHHHBBH4s4s', ip_header)

        version_ihl = iph[0]
        version = version_ihl >> 4
        ihl = version_ihl & 0xF

        iph_length = ihl * 4

        ttl = iph[5]
        protocol = iph[6]
        s_addr = socket.inet_ntoa(iph[8])
        d_addr = socket.inet_ntoa(iph[9])

        return [version_ihl,
                version,
                ihl,
                iph_length,
                ttl,
                protocol,
                s_addr,
                d_addr]

    def parse_tcp(self, packet, iph_length, eth_length):
        '''
        parse tcp_data and return source_port,
        dest_port and actual packet data
        '''
        p_len = iph_length + eth_length
        tcp_header = packet[p_len:p_len+20]

        # now unpack them:)
        tcph = unpack('!H HLLBBHHH', tcp_header)
        #  H     H     L   L   B   B      H   H   H
        #  2b    2b    4b  4b  1b  1b     2b  2b  2b
        #  sport dport seq ack res flags  win chk up
        # (22,   36513, 3701969065, 2346113113, 128, 24, 330, 33745, 0)
        source_port = tcph[0]

        dest_port = tcph[1]
        sequence = tcph[2]
        acknowledgement = tcph[3]
        doff_reserved = tcph[4]
        tcph_length = doff_reserved >> 4
        tcp_flags = tcph[5]

        h_size = eth_length + iph_length + tcph_length * 4
        data_size = len(packet) - h_size

        data = packet[h_size:]

        return source_port, dest_port, tcp_flags, data


class SaltNetstat(object):
    '''
    Reads /proc/net/tcp and returns all connections
    '''

    def proc_tcp(self):
        '''
        Read the table of tcp connections & remove header
        '''
        with open('/proc/net/tcp', 'r') as tcp_f:
            content = tcp_f.readlines()
            content.pop(0)
        return content

    def hex2dec(self, hex_s):
        '''
        convert hex to dezimal
        '''
        return str(int(hex_s, 16))

    def ip(self, hex_s):
        '''
        convert into readable ip
        '''
        ip = [(self.hex2dec(hex_s[6:8])),
              (self.hex2dec(hex_s[4:6])),
              (self.hex2dec(hex_s[2:4])),
              (self.hex2dec(hex_s[0:2]))]
        return '.'.join(ip)

    def remove_empty(self, array):
        '''
        create new list without empty entries
        '''
        return [x for x in array if x != '']

    def convert_ip_port(self, array):
        '''
        hex_ip:hex_port to str_ip:str_port
        '''
        host, port = array.split(':')
        return self.ip(host), self.hex2dec(port)

    def run(self):
        '''
        main loop for netstat
        '''
        while 1:
            ips = {
                    'ips/4505': {},
                    'ips/4506': {}
                  }
            content = self.proc_tcp()

            for line in content:
                line_array = self.remove_empty(line.split(' '))
                l_host, l_port = self.convert_ip_port(line_array[1])
                r_host, r_port = self.convert_ip_port(line_array[2])
                if l_port == '4505':
                    if r_host not in ips['ips/4505']:
                        ips['ips/4505'][r_host] = 0
                    ips['ips/4505'][r_host] += 1
                if l_port == '4506':
                    if r_host not in ips['ips/4506']:
                        ips['ips/4506'][r_host] = 0
                    ips['ips/4506'][r_host] += 1

            yield (len(ips['ips/4505']), len(ips['ips/4506']))
            time.sleep(0.5)


def filter_new_cons(packet):
    '''
    filter packets by there tcp-state and
    returns codes for specific states
    '''
    flags = []
    TCP_FIN = 0x01
    TCP_SYN = 0x02
    TCP_RST = 0x04
    TCP_PSH = 0x08
    TCP_ACK = 0x10
    TCP_URG = 0x20
    TCP_ECE = 0x40
    TCP_CWK = 0x80

    if packet['tcp']['flags'] & TCP_FIN:
        flags.append('FIN')
    elif packet['tcp']['flags'] & TCP_SYN:
        flags.append('SYN')
    elif packet['tcp']['flags'] & TCP_RST:
        flags.append('RST')
    elif packet['tcp']['flags'] & TCP_PSH:
        flags.append('PSH')
    elif packet['tcp']['flags'] & TCP_ACK:
        flags.append('ACK')
    elif packet['tcp']['flags'] & TCP_URG:
        flags.append('URG')
    elif packet['tcp']['flags'] & TCP_ECE:
        flags.append('ECE')
    elif packet['tcp']['flags'] & TCP_CWK:
        flags.append('CWK')
    else:
        print("UNKNOWN PACKET")

    if packet['tcp']['d_port'] == 4505:
        # track new connections
        if 'SYN' in flags and len(flags) == 1:
            return 10
        # track closing connections
        elif 'FIN' in flags:
            return 12

    elif packet['tcp']['d_port'] == 4506:
        # track new connections
        if 'SYN' in flags and len(flags) == 1:
            return 100
        # track closing connections
        elif 'FIN' in flags:
            return 120
    # packet does not match requirements
    else:
        return None


def main():
    '''
    main loop for whole script
    '''
    # passed parameters
    args = vars(ArgParser().parse_args())

    # reference timer for printing in intervals
    r_time = 0

    # the ports we want to monitor
    ports = [4505, 4506]

    print("Sniffing device {0}".format(args['iface']))

    stat = {
              '4506/new': 0,
              '4506/est': 0,
              '4506/fin': 0,
              '4505/new': 0,
              '4505/est': 0,
              '4505/fin': 0,
              'ips/4505': 0,
              'ips/4506': 0
            }

    if args['only_ip']:
        print(
               'IPs making new connections '
               '(ports:{0}, interval:{1})'.format(ports,
                                                  args['ival'])
             )
    else:
        print(
               'Salt-Master Network Status '
               '(ports:{0}, interval:{1})'.format(ports,
                                                  args['ival'])
             )
    try:
        while 1:
            s_time = int(time.time())

            packet = next(PCAPParser(args['iface']).run())

            p_state = filter_new_cons(packet)

            ips_auth = []
            ips_push = []

            # new connection to 4505
            if p_state == 10:
                stat['4505/new'] += 1
                if packet['ip']['s_addr'] not in ips_auth:
                    ips_auth.append(packet['ip']['s_addr'])
            # closing connection to 4505
            elif p_state == 12:
                stat['4505/fin'] += 1

            # new connection to 4506
            elif p_state == 100:
                stat['4506/new'] += 1
                if packet['ip']['s_addr'] not in ips_push:
                    ips_push.append(packet['ip']['s_addr'])
            # closing connection to 4506
            elif p_state == 120:
                stat['4506/fin'] += 1

            # get the established connections to 4505 and 4506
            # these would only show up in tcpdump if data is transferred
            # but then with different flags (PSH, etc.)
            stat['4505/est'], stat['4506/est'] = next(SaltNetstat().run())

            # print only in intervals
            if (s_time % args['ival']) == 0:
                # prevent printing within the same second
                if r_time != s_time:
                    if args['only_ip']:
                        msg = 'IPs/4505: {0}, IPs/4506: {1}'.format(len(ips_auth),
                                                                    len(ips_push))
                    else:
                        msg = "4505=>[ est: {0}, ".format(stat['4505/est'])
                        msg += "new: {0}/s, ".format(stat['4505/new'] / args['ival'])
                        msg += "fin: {0}/s ] ".format(stat['4505/fin'] / args['ival'])

                        msg += " 4506=>[ est: {0}, ".format(stat['4506/est'])
                        msg += "new: {0}/s, ".format(stat['4506/new'] / args['ival'])
                        msg += "fin: {0}/s ]".format(stat['4506/fin'] / args['ival'])

                    print(msg)

                    # reset the so far collected stats
                    for item in stat:
                        stat[item] = 0
                    r_time = s_time

    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == "__main__":
    main()

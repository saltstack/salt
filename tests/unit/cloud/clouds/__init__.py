# -*- coding: utf-8 -*-


def _preferred_ip(ip_set, preferred=None):
    '''
    Returns a function that reacts which ip is prefered
    :param ip_set:
    :param private:
    :return:
    '''

    def _ip_decider(vm, ips):
        for ip in ips:
            if ip in preferred:
                return ip
        return False

    return _ip_decider

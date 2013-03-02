from random import choice
from salt.exceptions import SaltClientError

try:
    from boto.ec2 import connect_to_region
    from boto.exception import EC2ResponseError
except ImportError:
    print "The boto library is required to make use of EC2 functionality."
    raise ImportError


def get_master_dns(opts):
    '''
    Returns a master IP given the EC2 filtering options provided
    '''

    access_key = opts.get('access_key', None)
    secret_key = opts.get('secret_key', None)
    region_name = opts.get('region_name', 'us-east-1')

    allow_multiple = opts.get('allow_multiple', False)
    resolve_via = opts.get('resolve_via', 'public_dns_name')

    filters = _construct_filters(opts.get('tags', {}))

    # Only get 'running' instances
    filters['instance-state-name'] = 'running'

    if not (access_key is None or secret_key is None):
        try:
            conn = connect_to_region(aws_access_key_id=access_key,
                                     aws_secret_access_key=secret_key,
                                     region_name=region_name)
            reservations = conn.get_all_instances(filters=filters)
        except EC2ResponseError:
            raise SaltClientError("Couldn't connect to EC2 with the given"
                                  " credentials. If you wish to use IAM roles"
                                  ", please remove the access_key and "
                                  "secret_key from the minion config.")
    else:
        # Try and use IAM Roles
        try:
            conn = connect_to_region(region_name=region_name)
            reservations = conn.get_all_instances(filters=filters)
        except EC2ResponseError:
            raise SaltClientError("Couldn't connect to EC2 using IAM roles."
                                  " If you were expecting to use Access Keys "
                                  "instead, please make sure they are "
                                  "properly configured in the ec2_info block.")

    instances = [instance for reservation in reservations
                 for instance in reservation.instances]

    if len(instances) < 1:
        raise SaltClientError("No EC2 instances returned for the given"
                              " filters.")
    elif len(instances) > 1 and not allow_multiple:
        raise SaltClientError("Multiple EC2 instances returned for the"
                              " given filters. If you'd like to pick a random"
                              " return IPs you should set `allow_multiple` to "
                              "True in ec2_info.")
    elif len(instances) > 1 and allow_multiple:
        hostname = getattr(choice(instances), resolve_via, None)
    else:
        hostname = getattr(instances[0], resolve_via, None)

    if hostname is None:
        raise SaltClientError("Couldn't get resolve_via ({0}) attribute on"
                              " returned instances.".format(resolve_via))

    return hostname


def _construct_filters(filters):
    '''
    Converts filters from minion config into something boto can use
    '''

    return_filters = {}

    for key, value in filters.iteritems():
        return_filters['tag:%s' % key] = value

    return return_filters

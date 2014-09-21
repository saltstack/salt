import pyrax

class Authenticate(object):
    def __init__(self, username, password, region, auth_endpoint=None, **kwargs):
        cloud_kwargs = {
            'tenant_name': username,
            'password': password,
            'region': region,
            'identity_type': kwargs.get('identity_type', 'keystone')
        }
        if auth_endpoint:
            cloud_kwargs['auth_endpoint'] = auth_endpoint

        pyrax.set_credentials(**cloud_kwargs)
        self.conn = pyrax.keyring_auth()

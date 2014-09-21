try:
    import pyrax
    from salt.utils.openstack.pyrax.authenticate import Authenticate

    __all__ = [
        Authenticate
    ]

    HAS_PYRAX = True
except ImportError as err:
    HAS_PYRAX = False

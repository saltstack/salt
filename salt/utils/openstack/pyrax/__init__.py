# pylint: disable=import-error
try:
    import pyrax
    from salt.utils.openstack.pyrax.authenticate import Authenticate
    from salt.utils.openstack.pyrax.queues import RackspaceQueues

    __all__ = ["Authenticate", "RackspaceQueues"]

    HAS_PYRAX = True
except ImportError as err:
    HAS_PYRAX = False
# pylint: enable=import-error

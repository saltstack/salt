"""
Retrieve EC2 instance data for minions for ec2_tags and ec2_tags_list

The minion id must be the AWS instance-id or value in ``tag_match_key``.  For
example set ``tag_match_key`` to ``Name`` to have the minion-id matched against
the tag 'Name'. The tag contents must be unique. The value of
``tag_match_value`` can be 'uqdn' or 'asis'. if 'uqdn', then the domain will be
stripped before comparison.

Additionally, the ``use_grain`` option can be set to ``True``. This allows the
use of an instance-id grain instead of the minion-id. Since this is a potential
security risk, the configuration can be further expanded to include a list of
minions that are trusted to only allow the alternate id of the instances to
specific hosts. There is no glob matching at this time.

.. note::
    If you are using ``use_grain: True`` in the configuration for this external
    pillar module, the minion must have :conf_minion:`metadata_server_grains`
    enabled in the minion config file (see also :py:mod:`here
    <salt.grains.metadata>`).

    It is important to also note that enabling the ``use_grain`` option allows
    the minion to manipulate the pillar data returned, as described above.

The optional ``tag_list_key`` indicates which keys should be added to
``ec2_tags_list`` and be split by ``tag_list_sep`` (by default ``;``). If a tag
key is included in ``tag_list_key`` it is removed from ec2_tags. If a tag does
not exist it is still included as an empty list.


.. note::
    As with any master configuration change, restart the salt-master daemon for
    changes to take effect.

.. code-block:: yaml

    ext_pillar:
      - ec2_pillar:
          tag_match_key: 'Name'
          tag_match_value: 'asis'
          tag_list_key:
            - Role
          tag_list_sep: ';'
          use_grain: True
          minion_ids:
            - trusted-minion-1
            - trusted-minion-2
            - trusted-minion-3

This is a very simple pillar configuration that simply retrieves the instance
data from AWS. Currently the only portion implemented are EC2 tags, which
returns a list of key/value pairs for all of the EC2 tags assigned to the
instance.
"""


import logging
import re

from salt.utils.versions import StrictVersion as _StrictVersion

try:
    import boto.ec2
    import boto.utils
    import boto.exception

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# Set up logging
log = logging.getLogger(__name__)

# DEBUG boto is far too verbose
logging.getLogger("boto").setLevel(logging.WARNING)


def __virtual__():
    """
    Check for required version of boto and make this pillar available
    depending on outcome.
    """
    if not HAS_BOTO:
        return False
    boto_version = _StrictVersion(boto.__version__)
    required_boto_version = _StrictVersion("2.8.0")
    if boto_version < required_boto_version:
        log.error(
            "%s: installed boto version %s < %s, can't retrieve instance data",
            __name__,
            boto_version,
            required_boto_version,
        )
        return False
    return True


def _get_instance_info():
    """
    Helper function to return the instance ID and region of the master where
    this pillar is run.
    """
    identity = boto.utils.get_instance_identity()["document"]
    return (identity["instanceId"], identity["region"])


def ext_pillar(
    minion_id,
    pillar,  # pylint: disable=W0613
    use_grain=False,
    minion_ids=None,
    tag_match_key=None,
    tag_match_value="asis",
    tag_list_key=None,
    tag_list_sep=";",
):
    """
    Execute a command and read the output as YAML
    """
    valid_tag_match_value = ["uqdn", "asis"]

    # meta-data:instance-id
    grain_instance_id = __grains__.get("meta-data", {}).get("instance-id", None)
    if not grain_instance_id:
        # dynamic:instance-identity:document:instanceId
        grain_instance_id = (
            __grains__.get("dynamic", {})
            .get("instance-identity", {})
            .get("document", {})
            .get("instance-id", None)
        )
    if (
        grain_instance_id
        and re.search(r"^i-([0-9a-z]{17}|[0-9a-z]{8})$", grain_instance_id) is None
    ):
        log.error(
            "External pillar %s, instance-id '%s' is not valid for '%s'",
            __name__,
            grain_instance_id,
            minion_id,
        )
        grain_instance_id = None  # invalid instance id found, remove it from use.

    # Check AWS Tag restrictions .i.e. letters, spaces, and numbers and + - = . _ : / @
    if tag_match_key and re.match(r"[\w=.:/@-]+$", tag_match_key) is None:
        log.error(
            "External pillar %s, tag_match_key '%s' is not valid ",
            __name__,
            tag_match_key if isinstance(tag_match_key, str) else "non-string",
        )
        return {}

    if tag_match_key and tag_match_value not in valid_tag_match_value:
        log.error(
            "External pillar %s, tag_value '%s' is not valid must be one of %s",
            __name__,
            tag_match_value,
            " ".join(valid_tag_match_value),
        )
        return {}

    if not tag_match_key:
        base_msg = (
            "External pillar %s, querying EC2 tags for minion id '%s' "
            "against instance-id",
            __name__,
            minion_id,
        )
    else:
        base_msg = (
            "External pillar %s, querying EC2 tags for minion id '%s' "
            "against instance-id or '%s' against '%s'",
            __name__,
            minion_id,
            tag_match_key,
            tag_match_value,
        )

    log.debug(base_msg)
    find_filter = None
    find_id = None

    if re.search(r"^i-([0-9a-z]{17}|[0-9a-z]{8})$", minion_id) is not None:
        find_filter = None
        find_id = minion_id
    elif tag_match_key:
        if tag_match_value == "uqdn":
            find_filter = {"tag:{}".format(tag_match_key): minion_id.split(".", 1)[0]}
        else:
            find_filter = {"tag:{}".format(tag_match_key): minion_id}
        if grain_instance_id:
            # we have an untrusted grain_instance_id, use it to narrow the search
            # even more. Combination will be unique even if uqdn is set.
            find_filter.update({"instance-id": grain_instance_id})
        # Add this if running state is not dependent on EC2Config
        # find_filter.update('instance-state-name': 'running')

    # no minion-id is instance-id and no suitable filter, try use_grain if enabled
    if not find_filter and not find_id and use_grain:
        if not grain_instance_id:
            log.debug(
                "Minion-id is not in AWS instance-id formation, and there "
                "is no instance-id grain for minion %s",
                minion_id,
            )
            return {}
        if minion_ids is not None and minion_id not in minion_ids:
            log.debug(
                "Minion-id is not in AWS instance ID format, and minion_ids "
                "is set in the ec2_pillar configuration, but minion %s is "
                "not in the list of allowed minions %s",
                minion_id,
                minion_ids,
            )
            return {}
        find_id = grain_instance_id

    if not (find_filter or find_id):
        log.debug(
            "External pillar %s, querying EC2 tags for minion id '%s' against "
            "instance-id or '%s' against '%s' noughthing to match against",
            __name__,
            minion_id,
            tag_match_key,
            tag_match_value,
        )
        return {}

    myself = boto.utils.get_instance_metadata(timeout=0.1, num_retries=1)
    if len(myself.keys()) < 1:
        log.info("%s: salt master not an EC2 instance, skipping", __name__)
        return {}

    # Get the Master's instance info, primarily the region
    (_, region) = _get_instance_info()

    # If the Minion's region is available, use it instead
    if use_grain:
        region = __grains__.get("ec2", {}).get("region", region)

    try:
        conn = boto.ec2.connect_to_region(region)
    except boto.exception.AWSConnectionError as exc:
        log.error("%s: invalid AWS credentials, %s", __name__, exc)
        return {}

    if conn is None:
        log.error("%s: Could not connect to region %s", __name__, region)
        return {}

    try:
        if find_id:
            instance_data = conn.get_only_instances(
                instance_ids=[find_id], dry_run=False
            )
        else:
            # filters and max_results can not be used togther.
            instance_data = conn.get_only_instances(filters=find_filter, dry_run=False)

    except boto.exception.EC2ResponseError as exc:
        log.error("%s failed with '%s'", base_msg, exc)
        return {}

    if not instance_data:
        log.debug(
            "%s no match using '%s'", base_msg, find_id if find_id else find_filter
        )
        return {}

    # Find a active instance, i.e. ignore terminated and stopped instances
    active_inst = []
    for idx, inst_data in enumerate(instance_data):
        if inst_data.state not in ["terminated", "stopped"]:
            active_inst.append(idx)

    valid_inst = len(active_inst)
    if not valid_inst:
        log.debug(
            "%s match found but not active '%s'",
            base_msg,
            find_id if find_id else find_filter,
        )
        return {}

    if valid_inst > 1:
        log.error(
            "%s multiple matches, ignored, using '%s'",
            base_msg,
            find_id if find_id else find_filter,
        )
        return {}

    instance = instance_data[active_inst[0]]
    if instance.tags:
        ec2_tags = instance.tags
        ec2_tags_list = {}
        log.debug(
            "External pillar %s, for minion id '%s', tags: %s",
            __name__,
            minion_id,
            instance.tags,
        )
        if tag_list_key and isinstance(tag_list_key, list):
            for item in tag_list_key:
                if item in ec2_tags:
                    ec2_tags_list[item] = ec2_tags[item].split(tag_list_sep)
                    del ec2_tags[item]  # make sure its only in ec2_tags_list
                else:
                    ec2_tags_list[item] = []  # always return a result

        return {"ec2_tags": ec2_tags, "ec2_tags_list": ec2_tags_list}
    return {}

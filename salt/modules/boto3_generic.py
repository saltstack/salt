import contextlib
import logging

import salt.utils.data
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


@contextlib.contextmanager
def lookup_resources(*args, region=None, keyid=None, key=None, profile=None):
    """
    Helper function to perform multiple lookups successively.

    :type args: dict or list(dict)
    :param args: One or more entries for attributes of resource
      types that should be looked up. The types shown are for a single resource.
      Provide a list to allow for multiple resources.
      The dictionary consists of:

        - service (str): Required. The name (in snake_case) of the AWS service
          to use. For example: ec2, elb, efs, dynamo_db. For a full listing, see:
          https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html
          Note that not all services are implemented.
        - name (str): Required. The name of the resource type to retrieve, in snake_case
          and singular form. For example: ``network_interface``.
        - as (str): Optional. The key to use in the result instead of ``name``.
          Used when multiple different resources of the same name need to be looked up.
          For example: ``requester_vpc`` and ``peer_vpc``.
        - kwargs (dict or list(dict)): Required. The kwargs to pass to ``lookup_resource``.
          You can pass alternate AWS IAM credentials (region, keyid, key) or profile
          if a specific resource needs to be looked up in another account, as can
          be the case with VPC peering connections.
          This can also be a list of dicts in order to do multiple lookups for the
          same resource_type. In this case, the returned data will be a dict of
          lists instead of a dict of values.
          This is used, for example, by :py:func:`accept_vpc_endpoint_connections`.
        - required (bool): Optional. Indication whether the resource lookup must be succesful.
          That is, this resource is a required resource. Default: ``True``
        - result_keys (str/list(str)): Optional. The key(s) to use with salt.utils.data.traverse_dict_and_list
          to extract the needed data element(s) from the result of ``boto3_{service}.lookup_{name}``.
          Default: UpperCamel(resource_type) + "Id"

      For example, ``disassociate_route_table`` needs an AssociationId, which
      is an attribute of a ``route_table`` that can be looked up by various
      arguments (see ``lookup_route_table``). For that, this argument could be:

      .. code-block:: python

          {
              'service': 'ec2',
              'name': 'route_table',
              'kwargs': {'route_table_name': 'My Name', 'association_subnet_id': 'subnet-1234'},
              'result_keys': 'RouteTableAssociationId'
          }

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict of looked up resources with dict of ``result_keys`` and its values.
      If ``result_keys`` contained no, or only one value, the return structure is:

      .. code-block:: python

          {'result': {name: result_value}}

      Otherwise, the return structure is:

      .. code-block:: python

          {'result': {name: {result_key: result_value}}}

    :raises: SaltInvocationError if any of the required arguments are missing or incorrect.
    """
    ret = {}
    lookup_results = {}
    for idx, item in enumerate(args):
        if not isinstance(item, dict):
            raise SaltInvocationError(
                "Expected dictionary for resource #{}, got {}.".format(idx, type(item))
            )
        for required_argument in ["service", "name", "kwargs"]:
            if item.get(required_argument) is None:
                raise SaltInvocationError(
                    'No "{}" specified in resource #{}.'.format(required_argument, idx)
                )
        name = item["name"]
        item_required = item.get("required", True)
        default_result_key = (
            salt.utils.stringutils.snake_to_camel_case(name, uppercamel=True) + "Id"
        )
        result_keys = item.get("result_keys", [default_result_key])
        lookup_kwargs = item["kwargs"]
        if result_keys is None:
            result_keys = [default_result_key]
        elif not isinstance(result_keys, list):
            result_keys = [result_keys]
        if not isinstance(lookup_kwargs, list):
            lookup_kwargs = [lookup_kwargs]
        for single_lookup_kwargs in lookup_kwargs:
            single_lookup_results = {}
            if single_lookup_kwargs is None:
                if item_required:
                    raise SaltInvocationError(
                        "lookup kwargs is not specified (is None)."
                    )
                continue
            if not isinstance(single_lookup_kwargs, dict):
                if item_required:
                    raise SaltInvocationError(
                        "lookup kwargs specified is not a dict but: {}".format(
                            type(single_lookup_kwargs)
                        )
                    )
                continue
            if not any(single_lookup_kwargs.values()):
                if item_required:
                    raise SaltInvocationError(
                        "lookup kwargs does not contain any values."
                    )
                continue
            single_lookup_kwargs_uc = {
                salt.utils.stringutils.snake_to_camel_case(item, uppercamel=True): value
                for item, value in single_lookup_kwargs.items()
            }
            if set(result_keys) <= set(single_lookup_kwargs_uc.keys()) and all(
                [single_lookup_kwargs_uc[result_key] for result_key in result_keys]
            ):
                # No lookup is neccesary, all result keys are present in single_lookup_kwargs with value
                if len(result_keys) == 1:
                    single_lookup_results = single_lookup_kwargs_uc[result_keys[0]]
                else:
                    single_lookup_results = {
                        result_key: single_lookup_kwargs_uc[result_key]
                        for result_key in result_keys
                    }
            else:
                lookup_function_name = "boto3_{}.lookup_{}".format(
                    item["service"], name
                )
                lookup_function = __salt__.get(lookup_function_name)
                if not lookup_function:
                    if item_required:
                        raise SaltInvocationError(
                            "The function {} is not available in salt at this moment."
                            "".format(lookup_function_name)
                        )
                    continue
                    # single_lookup_results = None
                else:
                    conn_kwargs = {
                        "region": single_lookup_kwargs.get("region", region),
                        "keyid": single_lookup_kwargs.get("keyid", keyid),
                        "key": single_lookup_kwargs.get("key", key),
                        "profile": single_lookup_kwargs.get("profile", profile),
                    }
                    client = __utils__["boto3.get_connection"](
                        item["service"], **conn_kwargs
                    )
                    try:
                        res = lookup_function(client=client, **single_lookup_kwargs)
                    except SaltInvocationError as exc:
                        res = {"error": "{}".format(exc)}
                    log.debug("lookup_resources: res: %s", res)
                    if "error" in res and item_required:
                        yield res
                        return
                    single_lookup_results = (
                        None
                        if "error" in res
                        else {
                            result_key: salt.utils.data.traverse_dict_and_list(
                                res["result"], result_key
                            )
                            for result_key in result_keys
                        }
                    )

                if len(result_keys) == 1 and single_lookup_results:
                    single_lookup_results = list(single_lookup_results.values())[0]
                log.debug(
                    "lookup_resources(%s):\n" "\t\tkwargs: %s\n" "\t\tresult: %s",
                    name,
                    single_lookup_kwargs,
                    single_lookup_results,
                )
            lookup_results[item.get("as", name)] = single_lookup_results
    ret["result"] = lookup_results
    log.debug("_lookup_resources: ret: %s", ret)
    yield ret

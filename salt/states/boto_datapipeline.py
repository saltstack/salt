"""
Manage Data Pipelines

.. versionadded:: 2016.3.0

Be aware that this interacts with Amazon's services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit AWS credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    datapipeline.keyid: GKTADJGHEIQSXMKKRBJ08H
    datapipeline.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

  myprofile:
    keyid: GKTADJGHEIQSXMKKRBJ08H
    key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    region: us-east-1

.. code-block:: yaml

  Ensure daily data pipeline exists:
    boto_datapipeline.present:
      - name: my-datapipeline
      - pipeline_objects:
          DefaultSchedule:
            name: Every 1 day
            fields:
              period: 1 Day
              type: Schedule
              startAt: FIRST_ACTIVATION_DATE_TIME
      - parameter_values:
          myDDBTableName: my-dynamo-table
"""

import copy
import datetime
import difflib

import salt.utils.data
import salt.utils.json


def __virtual__():
    """
    Only load if boto is available.
    """
    if "boto_datapipeline.create_pipeline" in __salt__:
        return "boto_datapipeline"
    return (False, "boto_datapipeline module could not be loaded")


def present(
    name,
    pipeline_objects=None,
    pipeline_objects_from_pillars="boto_datapipeline_pipeline_objects",
    parameter_objects=None,
    parameter_objects_from_pillars="boto_datapipeline_parameter_objects",
    parameter_values=None,
    parameter_values_from_pillars="boto_datapipeline_parameter_values",
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure the data pipeline exists with matching definition.

    name
        Name of the service to ensure a data pipeline exists for.

    pipeline_objects
        Pipeline objects to use. Will override objects read from pillars.

    pipeline_objects_from_pillars
        The pillar key to use for lookup.

    parameter_objects
        Parameter objects to use. Will override objects read from pillars.

    parameter_objects_from_pillars
        The pillar key to use for lookup.

    parameter_values
        Parameter values to use. Will override values read from pillars.

    parameter_values_from_pillars
        The pillar key to use for lookup.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    pipeline_objects = pipeline_objects or {}
    parameter_objects = parameter_objects or {}
    parameter_values = parameter_values or {}

    present, old_pipeline_definition = _pipeline_present_with_definition(
        name,
        _pipeline_objects(pipeline_objects_from_pillars, pipeline_objects),
        _parameter_objects(parameter_objects_from_pillars, parameter_objects),
        _parameter_values(parameter_values_from_pillars, parameter_values),
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if present:
        ret["comment"] = f"AWS data pipeline {name} present"
        return ret

    if __opts__["test"]:
        ret["comment"] = f"Data pipeline {name} is set to be created or updated"
        ret["result"] = None
        return ret

    result_create_pipeline = __salt__["boto_datapipeline.create_pipeline"](
        name,
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in result_create_pipeline:
        ret["result"] = False
        ret["comment"] = "Failed to create data pipeline {}: {}".format(
            name, result_create_pipeline["error"]
        )
        return ret

    pipeline_id = result_create_pipeline["result"]

    result_pipeline_definition = __salt__["boto_datapipeline.put_pipeline_definition"](
        pipeline_id,
        _pipeline_objects(pipeline_objects_from_pillars, pipeline_objects),
        parameter_objects=_parameter_objects(
            parameter_objects_from_pillars, parameter_objects
        ),
        parameter_values=_parameter_values(
            parameter_values_from_pillars, parameter_values
        ),
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in result_pipeline_definition:
        if _immutable_fields_error(result_pipeline_definition):
            # If update not possible, delete and retry
            result_delete_pipeline = __salt__["boto_datapipeline.delete_pipeline"](
                pipeline_id,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if "error" in result_delete_pipeline:
                ret["result"] = False
                ret["comment"] = "Failed to delete data pipeline {}: {}".format(
                    pipeline_id, result_delete_pipeline["error"]
                )
                return ret

            result_create_pipeline = __salt__["boto_datapipeline.create_pipeline"](
                name,
                name,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if "error" in result_create_pipeline:
                ret["result"] = False
                ret["comment"] = "Failed to create data pipeline {}: {}".format(
                    name, result_create_pipeline["error"]
                )
                return ret

            pipeline_id = result_create_pipeline["result"]

            result_pipeline_definition = __salt__[
                "boto_datapipeline.put_pipeline_definition"
            ](
                pipeline_id,
                _pipeline_objects(pipeline_objects_from_pillars, pipeline_objects),
                parameter_objects=_parameter_objects(
                    parameter_objects_from_pillars, parameter_objects
                ),
                parameter_values=_parameter_values(
                    parameter_values_from_pillars, parameter_values
                ),
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )

        if "error" in result_pipeline_definition:
            # Still erroring after possible retry
            ret["result"] = False
            ret["comment"] = "Failed to create data pipeline {}: {}".format(
                name, result_pipeline_definition["error"]
            )
            return ret

    result_activate_pipeline = __salt__["boto_datapipeline.activate_pipeline"](
        pipeline_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in result_activate_pipeline:
        ret["result"] = False
        ret["comment"] = "Failed to create data pipeline {}: {}".format(
            name, result_pipeline_definition["error"]
        )
        return ret

    pipeline_definition_result = __salt__["boto_datapipeline.get_pipeline_definition"](
        pipeline_id,
        version="active",
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in pipeline_definition_result:
        new_pipeline_definition = {}
    else:
        new_pipeline_definition = _standardize(pipeline_definition_result["result"])

    if not old_pipeline_definition:
        ret["changes"]["new"] = "Pipeline created."
        ret["comment"] = f"Data pipeline {name} created"
    else:
        ret["changes"]["diff"] = _diff(old_pipeline_definition, new_pipeline_definition)
        ret["comment"] = f"Data pipeline {name} updated"

    return ret


def _immutable_fields_error(result_pipeline_definition):
    """Return true if update pipeline failed due to immutable fields

    Some fields cannot be changed after a pipeline has been activated.

    http://docs.aws.amazon.com/datapipeline/latest/DeveloperGuide/dp-manage-pipeline-modify-console.html#dp-edit-pipeline-limits
    """
    for e in result_pipeline_definition["error"]:
        for e2 in e["errors"]:
            if "can not be changed" in e2:
                return True
    return False


def _pipeline_present_with_definition(
    name,
    expected_pipeline_objects,
    expected_parameter_objects,
    expected_parameter_values,
    region,
    key,
    keyid,
    profile,
):
    """
    Return true if the pipeline exists and the definition matches.

    name
        The name of the pipeline.

    expected_pipeline_objects
        Pipeline objects that must match the definition.

    expected_parameter_objects
        Parameter objects that must match the definition.

    expected_parameter_values
        Parameter values that must match the definition.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    """
    result_pipeline_id = __salt__["boto_datapipeline.pipeline_id_from_name"](
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in result_pipeline_id:
        return False, {}

    pipeline_id = result_pipeline_id["result"]
    pipeline_definition_result = __salt__["boto_datapipeline.get_pipeline_definition"](
        pipeline_id,
        version="active",
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in pipeline_definition_result:
        return False, {}

    pipeline_definition = _standardize(pipeline_definition_result["result"])

    pipeline_objects = pipeline_definition.get("pipelineObjects")
    parameter_objects = pipeline_definition.get("parameterObjects")
    parameter_values = pipeline_definition.get("parameterValues")

    present = (
        _recursive_compare(
            _cleaned(pipeline_objects), _cleaned(expected_pipeline_objects)
        )
        and _recursive_compare(parameter_objects, expected_parameter_objects)
        and _recursive_compare(parameter_values, expected_parameter_values)
    )
    return present, pipeline_definition


def _cleaned(_pipeline_objects):
    """Return standardized pipeline objects to be used for comparing

    Remove year, month, and day components of the startDateTime so that data
    pipelines with the same time of day but different days are considered
    equal.
    """
    pipeline_objects = copy.deepcopy(_pipeline_objects)
    for pipeline_object in pipeline_objects:
        if pipeline_object["id"] == "DefaultSchedule":
            for field_object in pipeline_object["fields"]:
                if field_object["key"] == "startDateTime":
                    start_date_time_string = field_object["stringValue"]
                    start_date_time = datetime.datetime.strptime(
                        start_date_time_string, "%Y-%m-%dT%H:%M:%S"
                    )
                    field_object["stringValue"] = start_date_time.strftime("%H:%M:%S")
    return pipeline_objects


def _recursive_compare(v1, v2):
    """
    Return v1 == v2. Compares list, dict, recursively.
    """
    if isinstance(v1, list):
        if v2 is None:
            v2 = []
        if len(v1) != len(v2):
            return False
        v1.sort(key=_id_or_key)
        v2.sort(key=_id_or_key)
        for x, y in zip(v1, v2):
            if not _recursive_compare(x, y):
                return False
        return True
    elif isinstance(v1, dict):
        if v2 is None:
            v2 = {}
        v1 = dict(v1)
        v2 = dict(v2)
        if sorted(v1) != sorted(v2):
            return False
        for k in v1:
            if not _recursive_compare(v1[k], v2[k]):
                return False
        return True
    else:
        return v1 == v2


def _id_or_key(list_item):
    """
    Return the value at key 'id' or 'key'.
    """
    if isinstance(list_item, dict):
        if "id" in list_item:
            return list_item["id"]
        if "key" in list_item:
            return list_item["key"]
    return list_item


def _diff(old_pipeline_definition, new_pipeline_definition):
    """
    Return string diff of pipeline definitions.
    """
    old_pipeline_definition.pop("ResponseMetadata", None)
    new_pipeline_definition.pop("ResponseMetadata", None)

    diff = salt.utils.data.decode(
        difflib.unified_diff(
            salt.utils.json.dumps(old_pipeline_definition, indent=4).splitlines(True),
            salt.utils.json.dumps(new_pipeline_definition, indent=4).splitlines(True),
        )
    )
    return "".join(diff)


def _standardize(structure):
    """
    Return standardized format for lists/dictionaries.

    Lists of dictionaries are sorted by the value of the dictionary at
    its primary key ('id' or 'key'). OrderedDict's are converted to
    basic dictionaries.
    """

    def mutating_helper(structure):
        if isinstance(structure, list):
            structure.sort(key=_id_or_key)
            for each in structure:
                mutating_helper(each)
        elif isinstance(structure, dict):
            structure = dict(structure)
            for k, v in structure.items():
                mutating_helper(k)
                mutating_helper(v)

    new_structure = copy.deepcopy(structure)
    mutating_helper(new_structure)
    return new_structure


def _pipeline_objects(pipeline_objects_from_pillars, pipeline_object_overrides):
    """
    Return a list of pipeline objects that compose the pipeline

    pipeline_objects_from_pillars
        The pillar key to use for lookup

    pipeline_object_overrides
        Pipeline objects to use. Will override objects read from pillars.
    """
    from_pillars = copy.deepcopy(__salt__["pillar.get"](pipeline_objects_from_pillars))
    from_pillars.update(pipeline_object_overrides)
    pipeline_objects = _standardize(_dict_to_list_ids(from_pillars))
    for pipeline_object in pipeline_objects:
        pipeline_object["fields"] = _properties_from_dict(pipeline_object["fields"])
    return pipeline_objects


def _parameter_objects(parameter_objects_from_pillars, parameter_object_overrides):
    """
    Return a list of parameter objects that configure the pipeline

    parameter_objects_from_pillars
        The pillar key to use for lookup

    parameter_object_overrides
        Parameter objects to use. Will override objects read from pillars.
    """
    from_pillars = copy.deepcopy(__salt__["pillar.get"](parameter_objects_from_pillars))
    from_pillars.update(parameter_object_overrides)
    parameter_objects = _standardize(_dict_to_list_ids(from_pillars))
    for parameter_object in parameter_objects:
        parameter_object["attributes"] = _properties_from_dict(
            parameter_object["attributes"]
        )
    return parameter_objects


def _parameter_values(parameter_values_from_pillars, parameter_value_overrides):
    """
    Return a dictionary of parameter values that configure the pipeline

    parameter_values_from_pillars
        The pillar key to use for lookup

    parameter_value_overrides
        Parameter values to use. Will override values read from pillars.
    """
    from_pillars = copy.deepcopy(__salt__["pillar.get"](parameter_values_from_pillars))
    from_pillars.update(parameter_value_overrides)
    parameter_values = _standardize(from_pillars)
    return _properties_from_dict(parameter_values, key_name="id")


def _dict_to_list_ids(objects):
    """
    Convert a dictionary to a list of dictionaries, where each element has
    a key value pair {'id': key}. This makes it easy to override pillar values
    while still satisfying the boto api.
    """
    list_with_ids = []
    for key, value in objects.items():
        element = {"id": key}
        element.update(value)
        list_with_ids.append(element)
    return list_with_ids


def _properties_from_dict(d, key_name="key"):
    """
    Transforms dictionary into pipeline object properties.

    The output format conforms to boto's specification.

    Example input:
        {
            'a': '1',
            'b': {
                'ref': '2'
            },
        }

    Example output:
        [
            {
                'key': 'a',
                'stringValue': '1',
            },
            {
                'key': 'b',
                'refValue': '2',
            },
        ]
    """
    fields = []
    for key, value in d.items():
        if isinstance(value, dict):
            fields.append({key_name: key, "refValue": value["ref"]})
        else:
            fields.append({key_name: key, "stringValue": value})
    return fields


def absent(name, region=None, key=None, keyid=None, profile=None):
    """
    Ensure a pipeline with the service_name does not exist

    name
        Name of the service to ensure a data pipeline does not exist for.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    result_pipeline_id = __salt__["boto_datapipeline.pipeline_id_from_name"](
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" not in result_pipeline_id:
        pipeline_id = result_pipeline_id["result"]
        if __opts__["test"]:
            ret["comment"] = f"Data pipeline {name} set to be deleted."
            ret["result"] = None
            return ret
        else:
            __salt__["boto_datapipeline.delete_pipeline"](
                pipeline_id,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            ret["changes"]["old"] = {"pipeline_id": pipeline_id}
            ret["changes"]["new"] = None
    else:
        ret["comment"] = f"AWS data pipeline {name} absent."

    return ret

# -*- coding: utf-8 -*-
'''
Manage Apigateway Rest APIs
=================

.. versionadded:: Carbon

Create and destroy rest apis depending on a swagger version 2 definition file.
Be aware that this interacts with Amazon's services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure Apigateway API exists:
        boto_apigateway.present:
            - name: myfunction
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os
import os.path
import hashlib
import re
import json
import yaml

# Import Salt Libs
import salt.utils
from salt.ext.six import string_types

# Import 3rd Party Libs

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_apigateway' if 'boto_apigateway.describe_apis' in __salt__ else False


def present(name, api_name, swagger_file, stage_name, api_key_required,
            lambda_integration_role, lambda_region=None, stage_variables=None,
            region=None, key=None, keyid=None, profile=None,
            lambda_funcname_format='{stage}_{api}_{resource}_{method}',
            authorization_type='NONE'):
    '''
    Ensure the spcified api_name with the corresponding swaggerfile is deployed to the
    given stage_name in AWS ApiGateway.

    this state currently only supports ApiGateway integration with AWS Lambda, and CORS support is
    handled through a Mock integration.

    There may be multiple deployments for the API object, each deployment is tagged with a description
    (i.e. unique label) in pretty printed json format consisting of the following key/values.
        {
            "api_name": api_name,
            "swagger_file": basename_of_swagger_file
            "swagger_file_md5sum": md5sum_of_swagger_file,
            "swagger_info_object": info_object_content_in_swagger_file
        }

    Please note that the name of the lambda function to be integrated will be derived
    via the provided lambda_funcname_format parameters:

        the default lambda_funcname_format is a string with the following substitutable keys:
        "{stage}_{api}_{resource}_{method}".  The user can choose to reorder the known keys.

        the stage key corresponds to the stage_name passed in.
        the api key corresponds to the api_name passed in.
        the resource corresponds to the resource path defined in the passed swagger file.
        the method corresponds to the method for a resource path defined in the passed swagger file.

        for the default lambda_funcname_format, given the following
        input:
            api_name = '  Test    Service'
            stage_name = 'alpha'
            basePath = '/api'
            path = '/a/{b}/c'
            method = 'POST'

        we will end up with the following Lambda Function Name that will be looked up:
            'test_service_alpha_a_b_c_post'

        The canconicalization of these input parameters is done in the following order:
            1) lambda_funcname_format is formatted with the input parameters as passed,
            2) resulting string is stripped for leading/trailing spaces,
            3) path paramter's curly braces are removed from the resource path,
            4) consecutive spaces and forward slashes in the paths are replaced with '_'
            5) consecutive '_' are replaced with '_'

    Please note that for error response handling, the swagger file must have an error response model
    with the following schema.  The lambda functions should throw exceptions for any non successful responses.
    An optional pattern field can be specified in errorMessage field to aid the response mapping from Lambda
    to the proper error return status codes.
        .. code-block:: yaml
            Error:
              type: object
              properties:
                stackTrace:
                  type: array
                  items:
                    type: array
                    items:
                      type: string
                  description: call stack
              errorType:
                type: string
                description: error type
              errorMessage:
                type: string
                description: |
                  Error message, will be matched based on pattern.
                  If no pattern is specified, the default pattern used for response mapping will be +*.

    name
        The name of the state definition

    api_name
        The name of the rest api that we want to ensure exists in AWS API Gateway

    swagger_file
        Name of the location of the swagger rest api definition file in YAML format.

    stage_name
        Name of the stage we want to be associated with the given api_name and swagger_file
        definition

    api_key_required
        True or False - whether the API Key is required to call API methods

    lambda_integration_role
        The name or ARN of the IAM role that the AWS ApiGateway assumes when it
        executes your lambda function to handle incoming requests

    lambda_region
        The region where we expect to find the lambda functions.  This is used to
        determine the region where we should look for the Lambda Function for
        integration purposes.  The region determination is based on the following
        priority:

        1) lambda_region as passed in (is not None)
        2) if lambda_region is None, use the region as if a boto_lambda function were
        executed without explicitly specifying lambda region.
        3) if region determined in (2) is different than the region used by
        boto_apigateway functions, a final lookup will be attempted using the
        boto_apigateway region.

    stage_variables
        A dict with variables and their values, or a pillar key (string) that
        contains a dict with variables and their values.
        key and values in the dict must be strings.  {'string': 'string'}

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    lambda_funcname_format
        Please review the earlier example for the usage.  The only substituable keys in the funcname
        format are {stage}, {api}, {resource}, {method}.
        Any other keys or positional subsitution parameters will be flagged as an invalid input.

    authorization_type
        This field can be either 'NONE', or 'AWS_IAM'.  This will be applied to all methods in the given
        swagger spec file.  Default is set to 'NONE'
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    try:
        common_args = dict([('region', region),
                            ('key', key),
                            ('keyid', keyid),
                            ('profile', profile)])

        # try to open the swagger file and basic validation
        swagger = _Swagger(api_name, stage_name,
                           lambda_funcname_format,
                           swagger_file, common_args)

        # retrieve stage variables
        stage_vars = _get_stage_variables(stage_variables)

        # verify if api and stage already exists
        ret = swagger.verify_api(ret)
        if ret.get('publish'):
            # there is a deployment label with signature matching the given api_name,
            # swagger file name, swagger file md5 sum, and swagger file info object
            # just reassociate the stage_name to the given deployment label.
            if __opts__['test']:
                ret['comment'] = ('[stage: {0}] will be reassociated to an already available '
                                  'deployment that matched the given [api_name: {1}] '
                                  'and [swagger_file: {2}].\n'
                                  'Stage variables will be set '
                                  'to {3}.'.format(stage_name, api_name, swagger_file, stage_vars))
                ret['result'] = None
                return ret
            return swagger.publish_api(ret, stage_vars)

        if ret.get('current'):
            # already at desired state for the stage, swagger_file, and api_name
            if __opts__['test']:
                ret['comment'] = ('[stage: {0}] is already at desired state with an associated '
                                  'deployment matching the given [api_name: {1}] '
                                  'and [swagger_file: {2}].\n'
                                  'Stage variables will be set '
                                  'to {3}.'.format(stage_name, api_name, swagger_file, stage_vars))
                ret['result'] = None
            return swagger.overwrite_stage_variables(ret, stage_vars)

        # there doesn't exist any previous deployments for the given swagger_file, we need
        # to redeploy the content of the swagger file to the api, models, and resources object
        # and finally create a new deployment and tie the stage_name to this new deployment
        if __opts__['test']:
            ret['comment'] = ('There is no deployment matching the given [api_name: {0}] '
                              'and [swagger_file: {1}].  A new deployment will be '
                              'created and the [stage_name: {2}] will then be associated '
                              'to the newly created deployment.\n'
                              'Stage variables will be set '
                              'to {3}.'.format(api_name, swagger_file, stage_name, stage_vars))
            ret['result'] = None
            return ret

        ret = swagger.deploy_api(ret)
        if ret.get('abort'):
            return ret

        ret = swagger.deploy_models(ret)
        if ret.get('abort'):
            return ret

        ret = swagger.deploy_resources(ret,
                                       api_key_required=api_key_required,
                                       lambda_integration_role=lambda_integration_role,
                                       lambda_region=lambda_region,
                                       authorization_type=authorization_type)
        if ret.get('abort'):
            return ret

        ret = swagger.publish_api(ret, stage_vars)

    except (ValueError, IOError) as e:
        ret['result'] = False
        ret['comment'] = '{0}'.format(e.args)

    return ret


def _get_stage_variables(stage_variables):
    '''
    Helper function to retrieve stage variables from pillars/options, if the
    input is a string
    '''
    ret = dict()
    if stage_variables is None:
        return ret

    if isinstance(stage_variables, string_types):
        if stage_variables in __opts__:
            ret = __opts__[stage_variables]
        master_opts = __pillar__.get('master', {})
        if stage_variables in master_opts:
            ret = master_opts[stage_variables]
        if stage_variables in __pillar__:
            ret = __pillar__[stage_variables]
    elif isinstance(stage_variables, dict):
        ret = stage_variables

    if not isinstance(ret, dict):
        ret = dict()

    return ret


def absent(name, api_name, stage_name, nuke_api=False, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the stage_name associated with the given api_name deployed by boto_apigateway's
    present state is removed.  If the currently associated deployment to the given stage_name has
    no other stages associated with it, the deployment will also be removed.

    name
        Name of the swagger file in YAML format

    api_name
        Name of the rest api on AWS ApiGateway to ensure is absent.

    stage_name
        Name of the stage to be removed irrespective of the swagger file content.
        If the current deployment associated with the stage_name has no other stages associated
        with it, the deployment will also be removed.

    nuke_api
        If True, removes the API itself only if there are no other stages associated with any other
        deployments once the given stage_name is removed.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    try:
        common_args = dict([('region', region),
                            ('key', key),
                            ('keyid', keyid),
                            ('profile', profile)])

        swagger = _Swagger(api_name, stage_name, '', None, common_args)

        if not swagger.restApiId:
            ret['comment'] = '[Rest API: {0}] does not exist.'.format(api_name)
            return ret

        if __opts__['test']:
            if nuke_api:
                ret['comment'] = ('[stage: {0}] will be deleted, if there are no other '
                                  'active stages, the [api: {1} will also be '
                                  'deleted.'.format(stage_name, api_name))
            else:
                ret['comment'] = ('[stage: {0}] will be deleted.'.format(stage_name))
            ret['result'] = None
            return ret

        ret = swagger.delete_stage(ret)

        if ret.get('abort'):
            return ret

        if nuke_api and swagger.no_more_deployments_remain():
            ret = swagger.delete_api(ret)

    except (ValueError, IOError) as e:
        ret['result'] = False
        ret['comment'] = '{0}'.format(e.args)

    return ret


# Helper Swagger Class for swagger version 2.0 API specification
def _gen_md5_filehash(fname):
    '''
    helper function to generate a md5 hash of the swagger definition file
    '''
    _hash = hashlib.md5()
    with salt.utils.fopen(fname, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            _hash.update(chunk)
    return _hash.hexdigest()


def _dict_to_json_pretty(d, sort_keys=True):
    '''
    helper function to generate pretty printed json output
    '''
    return json.dumps(d, indent=4, separators=(',', ': '), sort_keys=sort_keys)


# Heuristic on whether or not the property name loosely matches given set of 'interesting' factors
# If you are interested in IDs for example, 'id', 'blah_id', 'blahId' would all match
def _name_matches(name, matches):
    '''
    Helper function to see if given name has any of the patterns in given matches
    '''
    for m in matches:
        if name.endswith(m):
            return True
        if name.lower().endswith('_'+m.lower()):
            return True
        if name.lower() == m.lower():
            return True
    return False


def _object_reducer(o, names=('id', 'name', 'path', 'httpMethod',
                              'statusCode', 'Created', 'Deleted',
                              'Updated', 'Flushed', 'Associated', 'Disassociated')):
    '''
    Helper function to reduce the amount of information that will be kept in the change log
    for API GW related return values
    '''
    result = {}
    if isinstance(o, dict):
        for k, v in o.iteritems():
            if isinstance(v, dict):
                reduced = v if k == 'variables' else _object_reducer(v, names)
                if reduced or _name_matches(k, names):
                    result[k] = reduced
            elif isinstance(v, list):
                newlist = []
                for val in v:
                    reduced = _object_reducer(val, names)
                    if reduced or _name_matches(k, names):
                        newlist.append(reduced)
                if newlist:
                    result[k] = newlist
            else:
                if _name_matches(k, names):
                    result[k] = v
    return result


def _log_changes(ret, changekey, changevalue):
    '''
    For logging create/update/delete operations to AWS ApiGateway
    '''
    cl = ret['changes'].get('new', [])
    cl.append({changekey: _object_reducer(changevalue)})
    ret['changes']['new'] = cl
    return ret


def _log_error_and_abort(ret, obj):
    '''
    helper function to update errors in the return structure
    '''
    ret['result'] = False
    ret['abort'] = True
    if 'error' in obj:
        ret['comment'] = '{0}'.format(obj.get('error'))
    return ret


class _Swagger(object):
    '''
    this is a helper class that holds the swagger definition file and the associated logic
    related to how to interpret the file and apply it to AWS Api Gateway.

    The main interface to the outside world is in deploy_api, deploy_models, and deploy_resources
    methods.
    '''

    SWAGGER_OBJ_V2_FIELDS = ('swagger', 'info', 'host', 'basePath', 'schemes', 'consumes', 'produces',
                             'paths', 'definitions', 'parameters', 'responses', 'securityDefinitions',
                             'security', 'tags', 'externalDocs')
    # SWAGGER OBJECT V2 Fields that are required by boto apigateway states.
    SWAGGER_OBJ_V2_FIELDS_REQUIRED = ('swagger', 'info', 'basePath', 'schemes', 'paths', 'definitions')
    # SWAGGER OPERATION NAMES
    SWAGGER_OPERATION_NAMES = ('get', 'put', 'post', 'delete', 'options', 'head', 'patch')
    SWAGGER_VERSIONS_SUPPORTED = ('2.0',)

    # VENDOR SPECIFIC FIELD PATTERNS
    VENDOR_EXT_PATTERN = re.compile('^x-')

    # JSON_SCHEMA_REF
    JSON_SCHEMA_DRAFT_4 = 'http://json-schema.org/draft-04/schema#'

    # AWS integration templates for normal and options methods
    REQUEST_TEMPLATE = {'application/json':
                        '#set($inputRoot = $input.path(\'$\'))\n'
                        '{\n'
                        '"header_params" : {\n'
                        '#set ($map = $input.params().header)\n'
                        '#foreach( $param in $map.entrySet() )\n'
                        '"$param.key" : "$param.value" #if( $foreach.hasNext ), #end\n'
                        '#end\n'
                        '},\n'
                        '"query_params" : {\n'
                        '#set ($map = $input.params().querystring)\n'
                        '#foreach( $param in $map.entrySet() )\n'
                        '"$param.key" : "$param.value" #if( $foreach.hasNext ), #end\n'
                        '#end\n'
                        '},\n'
                        '"path_params" : {\n'
                        '#set ($map = $input.params().path)\n'
                        '#foreach( $param in $map.entrySet() )\n'
                        '"$param.key" : "$param.value" #if( $foreach.hasNext ), #end\n'
                        '#end\n'
                        '},\n'
                        '"apigw_context" : {\n'
                        '"apiId": "$context.apiId",\n'
                        '"httpMethod": "$context.httpMethod",\n'
                        '"requestId": "$context.requestId",\n'
                        '"resourceId": "$context.resourceId",\n'
                        '"resourcePath": "$context.resourcePath",\n'
                        '"stage": "$context.stage",\n'
                        '"identity": {\n'
                        '  "user":"$context.identity.user",\n'
                        '  "userArn":"$context.identity.userArn",\n'
                        '  "userAgent":"$context.identity.userAgent",\n'
                        '  "sourceIp":"$context.identity.sourceIp",\n'
                        '  "cognitoIdentityId":"$context.identity.cognitoIdentityId",\n'
                        '  "cognitoIdentityPoolId":"$context.identity.cognitoIdentityPoolId",\n'
                        '  "cognitoAuthenticationType":"$context.identity.cognitoAuthenticationType",\n'
                        '  "cognitoAuthenticationProvider":["$util.escapeJavaScript($context.identity.cognitoAuthenticationProvider)"],\n'
                        '  "caller":"$context.identity.caller",\n'
                        '  "apiKey":"$context.identity.apiKey",\n'
                        '  "accountId":"$context.identity.accountId"\n'
                        '}\n'
                        '},\n'
                        '"body_params" : $input.json(\'$\'),\n'
                        '"stage_variables" : "$stageVariables"\n'
                        '}'}
    REQUEST_OPTION_TEMPLATE = {'application/json': '{"statusCode": 200}'}

    # AWS integration response template mapping to convert stackTrace part or the error
    # to a uniform format containing strings only. Swagger does not seem to allow defining
    # an array of non-uniform types, to it is not possible to create error model to match
    # exactly what comes out of lambda functions in case of error.
    RESPONSE_TEMPLATE = {'application/json':
                         '#set($inputRoot = $input.path(\'$\'))\n'
                         '{\n'
                         '  "errorMessage" : "$inputRoot.errorMessage",\n'
                         '  "errorType" : "$inputRoot.errorType",\n'
                         '  "stackTrace" : [\n'
                         '#foreach($stackTrace in $inputRoot.stackTrace)\n'
                         '    [\n'
                         '#foreach($elem in $stackTrace)\n'
                         '      "$elem"\n'
                         '#if($foreach.hasNext),#end\n'
                         '#end\n'
                         '    ]\n'
                         '#if($foreach.hasNext),#end\n'
                         '#end\n'
                         '  ]\n'
                         '}'}
    RESPONSE_OPTION_TEMPLATE = {}

    # This string should not be modified, every API created by this state will carry the description
    # below.
    AWS_API_DESCRIPTION = _dict_to_json_pretty({"provisioned_by": "Salt boto_apigateway.present State",
                                                "context": "See deployment or stage description"})

    class SwaggerParameter(object):
        '''
        This is a helper class for the Swagger Parameter Object
        '''
        LOCATIONS = ('body', 'query', 'header', 'path')

        def __init__(self, paramdict):
            self._paramdict = paramdict

        @property
        def location(self):
            '''
            returns location in the swagger parameter object
            '''
            _location = self._paramdict.get('in')
            if _location in _Swagger.SwaggerParameter.LOCATIONS:
                return _location
            raise ValueError('Unsupported parameter location: {0} in Parameter Object'.format(_location))

        @property
        def name(self):
            '''
            returns parameter name in the swagger parameter object
            '''
            _name = self._paramdict.get('name')
            if _name:
                if self.location == 'header':
                    return 'method.request.header.{0}'.format(_name)
                elif self.location == 'query':
                    return 'method.request.querystring.{0}'.format(_name)
                elif self.location == 'path':
                    return 'method.request.path.{0}'.format(_name)
                return None
            raise ValueError('Parameter must have a name: {0}'.format(_dict_to_json_pretty(self._paramdict)))

        @property
        def schema(self):
            '''
            returns the name of the schema given the reference in the swagger parameter object
            '''
            if self.location == 'body':
                _schema = self._paramdict.get('schema')
                if _schema:
                    if '$ref' in _schema:
                        schema_name = _schema.get('$ref').split('/')[-1]
                        return schema_name
                    raise ValueError(('Body parameter must have a JSON reference '
                                      'to the schema definition due to Amazon API restrictions: {0}'.format(self.name)))
                raise ValueError('Body parameter must have a schema: {0}'.format(self.name))
            return None

    class SwaggerMethodResponse(object):
        '''
        Helper class for Swagger Method Response Object
        '''
        def __init__(self, r):
            self._r = r

        @property
        def schema(self):
            '''
            returns the name of the schema given the reference in the swagger method response object
            '''
            _schema = self._r.get('schema')
            if _schema:
                if '$ref' in _schema:
                    return _schema.get('$ref').split('/')[-1]
                raise ValueError(('Method response must have a JSON reference '
                                  'to the schema definition: {0}'.format(_schema)))
            return None

        @property
        def headers(self):
            '''
            returns the headers dictionary in the method response object
            '''
            _headers = self._r.get('headers', {})
            return _headers

    def __init__(self, api_name, stage_name, lambda_funcname_format,
                 swagger_file_path, common_aws_args):
        self._api_name = api_name
        self._stage_name = stage_name
        self._lambda_funcname_format = lambda_funcname_format
        self._common_aws_args = common_aws_args
        self._restApiId = ''
        self._deploymentId = ''

        if swagger_file_path is not None:
            if os.path.exists(swagger_file_path) and os.path.isfile(swagger_file_path):
                self._swagger_file = swagger_file_path
                self._md5_filehash = _gen_md5_filehash(self._swagger_file)
                with salt.utils.fopen(self._swagger_file, 'rb') as sf:
                    self._cfg = yaml.load(sf)
                self._swagger_version = ''
            else:
                raise IOError('Invalid swagger file path, {0}'.format(swagger_file_path))

            self._validate_swagger_file()

        self._validate_lambda_funcname_format()

        self._resolve_api_id()

    def _is_http_error_rescode(self, code):
        '''
        Helper function to determine if the passed code is in the 400~599 range of http error
        codes
        '''
        return bool(re.match(r'^\s*[45]\d\d\s*$', code))

    def _validate_error_response_model(self, paths, mods):
        '''
        Helper function to help validate the convention established in the swagger file on how
        to handle response code mapping/integration
        '''
        for path, ops in paths:
            for opname, opobj in ops.iteritems():
                if opname not in _Swagger.SWAGGER_OPERATION_NAMES:
                    continue

                if 'responses' not in opobj:
                    raise ValueError('missing mandatory responses field in path item object')
                for rescode, resobj in opobj.get('responses').iteritems():
                    if not self._is_http_error_rescode(str(rescode)):
                        continue

                    # only check for response code from 400-599
                    if 'schema' not in resobj:
                        raise ValueError('missing schema field in path {0}, '
                                         'op {1}, response {2}'.format(path, opname, rescode))

                    schemaobj = resobj.get('schema')
                    if '$ref' not in schemaobj:
                        raise ValueError('missing $ref field under schema in '
                                         'path {0}, op {1}, response {2}'.format(path, opname, rescode))
                    schemaobjref = schemaobj.get('$ref', '/')
                    modelname = schemaobjref.split('/')[-1]

                    if modelname not in mods:
                        raise ValueError('model schema {0} reference not found '
                                         'under /definitions'.format(schemaobjref))
                    model = mods.get(modelname)

                    if model.get('type') != 'object':
                        raise ValueError('model schema {0} must be type object'.format(modelname))
                    if 'properties' not in model:
                        raise ValueError('model schema {0} must have properties fields'.format(modelname))

                    modelprops = model.get('properties')
                    if 'errorMessage' not in modelprops:
                        raise ValueError('model schema {0} must have errorMessage as a property to '
                                         'match AWS convention. If pattern is not set, .+ will '
                                         'be used'.format(modelname))

    def _validate_lambda_funcname_format(self):
        try:
            if self._lambda_funcname_format:
                known_kwargs = dict(stage='',
                                    api='',
                                    resource='',
                                    method='')
                self._lambda_funcname_format.format(**known_kwargs)
            return True
        except:
            raise ValueError('Invalid lambda_funcname_format {0}.  Please review '
                             'documentation for known substitutable keys'.format(self._lambda_funcname_format))

    def _validate_swagger_file(self):
        '''
        High level check/validation of the input swagger file based on
        https://github.com/swagger-api/swagger-spec/blob/master/versions/2.0.md

        This is not a full schema compliance check, but rather make sure that the input file (YAML or
        JSON) can be read into a dictionary, and we check for the content of the Swagger Object for version
        and info.
        '''

        # check for any invalid fields for Swagger Object V2
        for field in self._cfg:
            if (field not in _Swagger.SWAGGER_OBJ_V2_FIELDS and
                    not _Swagger.VENDOR_EXT_PATTERN.match(field)):
                raise ValueError('Invalid Swagger Object Field: {0}'.format(field))

        # check for Required Swagger fields by Saltstack boto apigateway state
        for field in _Swagger.SWAGGER_OBJ_V2_FIELDS_REQUIRED:
            if field not in self._cfg:
                raise ValueError('Missing Swagger Object Field: {0}'.format(field))

        # check for Swagger Version
        self._swagger_version = self._cfg.get('swagger')
        if self._swagger_version not in _Swagger.SWAGGER_VERSIONS_SUPPORTED:
            raise ValueError('Unsupported Swagger version: {0},'
                             'Supported versions are {1}'.format(self._swagger_version,
                                                                 _Swagger.SWAGGER_VERSIONS_SUPPORTED))

        log.info(type(self._models))
        self._validate_error_response_model(self.paths, self._models())

    @property
    def md5_filehash(self):
        '''
        returns md5 hash for the swagger file
        '''
        return self._md5_filehash

    @property
    def info(self):
        '''
        returns the swagger info object as a dictionary
        '''
        info = self._cfg.get('info')
        if not info:
            raise ValueError('Info Object has no values')
        return info

    @property
    def info_json(self):
        '''
        returns the swagger info object as a pretty printed json string.
        '''
        return _dict_to_json_pretty(self.info)

    @property
    def rest_api_name(self):
        '''
        returns the name of the api
        '''
        return self._api_name

    @property
    def rest_api_version(self):
        '''
        returns the version field in the swagger info object
        '''
        version = self.info.get('version')
        if not version:
            raise ValueError('Missing version value in Info Object')

        return version

    def _models(self):
        '''
        returns an iterator for the models specified in the swagger file
        '''
        models = self._cfg.get('definitions')
        if not models:
            raise ValueError('Definitions Object has no values, You need to define them in your swagger file')

        return models

    def models(self):
        '''
        generator to return the tuple of model and its schema to create on aws.
        '''
        model_dict = self._build_all_dependencies()
        while True:
            model = self._get_model_without_dependencies(model_dict)
            if not model:
                break
            yield (model, self._models().get(model))

    @property
    def paths(self):
        '''
        returns an iterator for the relative resource paths specified in the swagger file
        '''
        paths = self._cfg.get('paths')
        if not paths:
            raise ValueError('Paths Object has no values, You need to define them in your swagger file')
        for path in paths:
            if not path.startswith('/'):
                raise ValueError('Path object {0} should start with /. Please fix it'.format(path))
        return paths.iteritems()

    @property
    def basePath(self):
        '''
        returns the base path field as defined in the swagger file
        '''
        basePath = self._cfg.get('basePath', '')
        return basePath

    @property
    def restApiId(self):
        '''
        returns the rest api id as returned by AWS on creation of the rest api
        '''
        return self._restApiId

    @restApiId.setter
    def restApiId(self, restApiId):
        '''
        allows the assignment of the rest api id on creation of the rest api
        '''
        self._restApiId = restApiId

    @property
    def deployment_label_json(self):
        '''
        this property returns the unique description in pretty printed json for
        a particular api deployment
        '''
        return _dict_to_json_pretty(self.deployment_label)

    @property
    def deployment_label(self):
        '''
        this property returns the deployment label dictionary (mainly used by
        stage description)
        '''
        label = dict()

        label['swagger_info_object'] = self.info
        label['api_name'] = self.rest_api_name
        label['swagger_file'] = os.path.basename(self._swagger_file)
        label['swagger_file_md5sum'] = self.md5_filehash

        return label

    # methods to interact with boto_apigateway execution modules
    def _one_or_more_stages_remain(self, deploymentId):
        '''
        Helper function to find whether there are other stages still associated with a deployment
        '''
        stages = __salt__['boto_apigateway.describe_api_stages'](restApiId=self.restApiId,
                                                                 deploymentId=deploymentId,
                                                                 **self._common_aws_args).get('stages')
        return bool(stages)

    def no_more_deployments_remain(self):
        '''
        Helper function to find whether there are deployments left with stages associated
        '''
        no_more_deployments = True
        deployments = __salt__['boto_apigateway.describe_api_deployments'](restApiId=self.restApiId,
                                                                           **self._common_aws_args).get('deployments')
        if deployments:
            for deployment in deployments:
                deploymentId = deployment.get('id')
                stages = __salt__['boto_apigateway.describe_api_stages'](restApiId=self.restApiId,
                                                                         deploymentId=deploymentId,
                                                                         **self._common_aws_args).get('stages')
                if stages:
                    no_more_deployments = False
                    break

        return no_more_deployments

    def _get_current_deployment_id(self):
        '''
        Helper method to find the deployment id that the stage name is currently assocaited with.
        '''
        deploymentId = ''
        stage = __salt__['boto_apigateway.describe_api_stage'](restApiId=self.restApiId,
                                                               stageName=self._stage_name,
                                                               **self._common_aws_args).get('stage')
        if stage:
            deploymentId = stage.get('deploymentId')
        return deploymentId

    def _get_current_deployment_label(self):
        '''
        Helper method to find the deployment label that the stage_name is currently associated with.
        '''
        deploymentId = self._get_current_deployment_id()
        deployment = __salt__['boto_apigateway.describe_api_deployment'](restApiId=self.restApiId,
                                                                         deploymentId=deploymentId,
                                                                         **self._common_aws_args).get('deployment')
        if deployment:
            return deployment.get('description')
        return None

    def _get_desired_deployment_id(self):
        '''
        Helper method to return the deployment id matching the desired deployment label for
        this Swagger object based on the given api_name, swagger_file
        '''
        deployments = __salt__['boto_apigateway.describe_api_deployments'](restApiId=self.restApiId,
                                                                           **self._common_aws_args).get('deployments')
        if deployments:
            for deployment in deployments:
                if deployment.get('description') == self.deployment_label_json:
                    return deployment.get('id')
        return ''

    def overwrite_stage_variables(self, ret, stage_variables):
        '''
        overwrite the given stage_name's stage variables with the given stage_variables
        '''
        res = __salt__['boto_apigateway.overwrite_api_stage_variables'](restApiId=self.restApiId,
                                                                        stageName=self._stage_name,
                                                                        variables=stage_variables,
                                                                        **self._common_aws_args)

        if not res.get('overwrite'):
            ret['result'] = False
            ret['abort'] = True
            ret['common'] = res.get('error')
        else:
            ret = _log_changes(ret,
                               'overwrite_stage_variables',
                               res.get('stage'))
        return ret

    def _set_current_deployment(self, stage_desc_json, stage_variables):
        '''
        Helper method to associate the stage_name to the given deploymentId and make this current
        '''
        stage = __salt__['boto_apigateway.describe_api_stage'](restApiId=self.restApiId,
                                                               stageName=self._stage_name,
                                                               **self._common_aws_args).get('stage')
        if not stage:
            stage = __salt__['boto_apigateway.create_api_stage'](restApiId=self.restApiId,
                                                                 stageName=self._stage_name,
                                                                 deploymentId=self._deploymentId,
                                                                 description=stage_desc_json,
                                                                 variables=stage_variables,
                                                                 **self._common_aws_args)
            if not stage.get('stage'):
                return {'set': False, 'error': stage.get('error')}
        else:
            # overwrite the stage variables
            overwrite = __salt__['boto_apigateway.overwrite_api_stage_variables'](restApiId=self.restApiId,
                                                                                  stageName=self._stage_name,
                                                                                  variables=stage_variables,
                                                                                  **self._common_aws_args)
            if not overwrite.get('stage'):
                return {'set': False, 'error': overwrite.get('error')}

        return __salt__['boto_apigateway.activate_api_deployment'](restApiId=self.restApiId,
                                                                   stageName=self._stage_name,
                                                                   deploymentId=self._deploymentId,
                                                                   **self._common_aws_args)

    def _resolve_api_id(self):
        '''
        returns an Api Id that matches the given api_name and the hardcoded _Swagger.AWS_API_DESCRIPTION
        as the api description
        '''
        apis = __salt__['boto_apigateway.describe_apis'](name=self.rest_api_name,
                                                         description=_Swagger.AWS_API_DESCRIPTION,
                                                         **self._common_aws_args).get('restapi')
        if apis:
            if len(apis) == 1:
                self.restApiId = apis[0].get('id')
            else:
                raise ValueError('Multiple APIs matching given name {0} and '
                                 'description {1}'.format(self.rest_api_name, self.info_json))

    def delete_stage(self, ret):
        '''
        Method to delete the given stage_name.  If the current deployment tied to the given
        stage_name has no other stages associated with it, the deployment will be removed
        as well
        '''
        deploymentId = self._get_current_deployment_id()
        if deploymentId:
            result = __salt__['boto_apigateway.delete_api_stage'](restApiId=self.restApiId,
                                                                  stageName=self._stage_name,
                                                                  **self._common_aws_args)
            if not result.get('deleted'):
                ret['abort'] = True
                ret['result'] = False
                ret['comment'] = 'delete_stage delete_api_stage, {0}'.format(result.get('error'))
            else:
                # check if it is safe to delete the deployment as well.
                if not self._one_or_more_stages_remain(deploymentId):
                    result = __salt__['boto_apigateway.delete_api_deployment'](restApiId=self.restApiId,
                                                                               deploymentId=deploymentId,
                                                                               **self._common_aws_args)
                    if not result.get('deleted'):
                        ret['abort'] = True
                        ret['result'] = False
                        ret['comment'] = 'delete_stage delete_api_deployment, {0}'.format(result.get('error'))
                else:
                    ret['comment'] = 'stage {0} has been deleted.\n'.format(self._stage_name)
        else:
            # no matching stage_name/deployment found
            ret['comment'] = 'stage {0} does not exist'.format(self._stage_name)

        return ret

    def verify_api(self, ret):
        '''
        this method helps determine if the given stage_name is already on a deployment
        label matching the input api_name, swagger_file.

        If yes, returns abort with comment indicating already at desired state.
        If not and there is previous deployment labels in AWS matching the given input api_name and
        swagger file, indicate to the caller that we only need to reassociate stage_name to the
        previously existing deployment label.
        '''

        if self.restApiId:
            deployed_label_json = self._get_current_deployment_label()
            if deployed_label_json == self.deployment_label_json:
                ret['comment'] = ('Already at desired state, the stage {0} is already at the desired '
                                  'deployment label:\n{1}'.format(self._stage_name, deployed_label_json))
                ret['current'] = True
                return ret
            else:
                self._deploymentId = self._get_desired_deployment_id()
                if self._deploymentId:
                    ret['publish'] = True
        return ret

    def publish_api(self, ret, stage_variables):
        '''
        this method tie the given stage_name to a deployment matching the given swagger_file
        '''
        stage_desc = dict()
        stage_desc['current_deployment_label'] = self.deployment_label
        stage_desc_json = _dict_to_json_pretty(stage_desc)

        if self._deploymentId:
            # just do a reassociate of stage_name to an already existing deployment
            res = self._set_current_deployment(stage_desc_json, stage_variables)
            if not res.get('set'):
                ret['abort'] = True
                ret['result'] = False
                ret['common'] = res.get('error')
            else:
                ret = _log_changes(ret,
                                   'publish_api (reassociate deployment, set stage_variables)',
                                   res.get('response'))
        else:
            # no deployment existed for the given swagger_file for this Swagger object
            res = __salt__['boto_apigateway.create_api_deployment'](restApiId=self.restApiId,
                                                                    stageName=self._stage_name,
                                                                    stageDescription=stage_desc_json,
                                                                    description=self.deployment_label_json,
                                                                    variables=stage_variables,
                                                                    **self._common_aws_args)
            if not res.get('created'):
                ret['abort'] = True
                ret['result'] = False
                ret['common'] = res.get('error')
            else:
                ret = _log_changes(ret, 'publish_api (new deployment)', res.get('deployment'))
        return ret

    def _cleanup_api(self):
        '''
        Helper method to clean up resources and models if we detected a change in the swagger file
        for a stage
        '''
        resources = __salt__['boto_apigateway.describe_api_resources'](restApiId=self.restApiId,
                                                                       **self._common_aws_args)
        if resources.get('resources'):
            res = resources.get('resources')[1:]
            res.reverse()
            for resource in res:
                delres = __salt__['boto_apigateway.delete_api_resources'](restApiId=self.restApiId,
                                                                          path=resource.get('path'),
                                                                          **self._common_aws_args)
                if not delres.get('deleted'):
                    return delres

        models = __salt__['boto_apigateway.describe_api_models'](restApiId=self.restApiId, **self._common_aws_args)
        if models.get('models'):
            for model in models.get('models'):
                delres = __salt__['boto_apigateway.delete_api_model'](restApiId=self.restApiId,
                                                                      modelName=model.get('name'),
                                                                      **self._common_aws_args)
                if not delres.get('deleted'):
                    return delres

        return {'deleted': True}

    def deploy_api(self, ret):
        '''
        this method create the top level rest api in AWS apigateway
        '''
        if self.restApiId:
            res = self._cleanup_api()
            if not res.get('deleted'):
                ret['comment'] = 'Failed to cleanup restAreId {0}'.format(self.restApiId)
                ret['abort'] = True
                ret['result'] = False
                return ret
            return ret

        response = __salt__['boto_apigateway.create_api'](name=self.rest_api_name,
                                                          description=_Swagger.AWS_API_DESCRIPTION,
                                                          **self._common_aws_args)

        if not response.get('created'):
            ret['result'] = False
            ret['abort'] = True
            if 'error' in response:
                ret['comment'] = 'Failed to create rest api: {0}.'.format(response['error']['message'])
            return ret

        self.restApiId = response.get('restapi', {}).get('id')

        return _log_changes(ret, 'deploy_api', response.get('restapi'))

    def delete_api(self, ret):
        '''
        Method to delete a Rest Api named defined in the swagger file's Info Object's title value.

        ret
            a dictionary for returning status to Saltstack
        '''

        exists_response = __salt__['boto_apigateway.api_exists'](name=self.rest_api_name,
                                                                 description=_Swagger.AWS_API_DESCRIPTION,
                                                                 **self._common_aws_args)
        if exists_response.get('exists'):
            if __opts__['test']:
                ret['comment'] = 'Rest API named {0} is set to be deleted.'.format(self.rest_api_name)
                ret['result'] = None
                ret['abort'] = True
                return ret

            delete_api_response = __salt__['boto_apigateway.delete_api'](name=self.rest_api_name,
                                                                         description=_Swagger.AWS_API_DESCRIPTION,
                                                                         **self._common_aws_args)
            if not delete_api_response.get('deleted'):
                ret['result'] = False
                ret['abort'] = True
                if 'error' in delete_api_response:
                    ret['comment'] = 'Failed to delete rest api: {0}.'.format(delete_api_response['error']['message'])
                return ret

            ret = _log_changes(ret, 'delete_api', delete_api_response)
        else:
            ret['comment'] = ('api already absent for swagger file: '
                              '{0}, desc: {1}'.format(self.rest_api_name, self.info_json))

        return ret

    def _aws_model_ref_from_swagger_ref(self, r):
        '''
        Helper function to reference models created on aws apigw
        '''
        model_name = r.split('/')[-1]
        return 'https://apigateway.amazonaws.com/restapis/{0}/models/{1}'.format(self.restApiId, model_name)

    def _update_schema_to_aws_notation(self, schema):
        '''
        Helper function to map model schema to aws notation
        '''
        result = {}
        for k, v in schema.items():
            if k == '$ref':
                v = self._aws_model_ref_from_swagger_ref(v)
            if isinstance(v, dict):
                v = self._update_schema_to_aws_notation(v)
            result[k] = v
        return result

    def _build_dependent_model_list(self, obj_schema):
        '''
        Helper function to build the list of models the given object schema is referencing.
        '''
        dep_models_list = []

        if obj_schema:
            obj_schema['type'] = obj_schema.get('type', 'object')
        if obj_schema['type'] == 'array':
            dep_models_list.extend(self._build_dependent_model_list(obj_schema.get('items', {})))
        else:
            ref = obj_schema.get('$ref')
            if ref:
                ref_obj_model = ref.split("/")[-1]
                ref_obj_schema = self._models().get(ref_obj_model)
                dep_models_list.extend(self._build_dependent_model_list(ref_obj_schema))
                dep_models_list.extend([ref_obj_model])
            else:
                # need to walk each property object
                properties = obj_schema.get('properties')
                if properties:
                    for _, prop_obj_schema in properties.iteritems():
                        dep_models_list.extend(self._build_dependent_model_list(prop_obj_schema))
        return list(set(dep_models_list))

    def _build_all_dependencies(self):
        '''
        Helper function to build a map of model to their list of model reference dependencies
        '''
        ret = {}
        for model, schema in self._models().iteritems():
            dep_list = self._build_dependent_model_list(schema)
            ret[model] = dep_list
        return ret

    def _get_model_without_dependencies(self, models_dict):
        '''
        Helper function to find the next model that should be created
        '''
        next_model = None
        if not models_dict:
            return next_model

        for model, dependencies in models_dict.iteritems():
            if dependencies == []:
                next_model = model
                break

        if next_model is None:
            raise ValueError('incomplete model definitions, models in dependency '
                             'list not defined: {0}'.format(models_dict))

        # remove the model from other depednencies before returning
        models_dict.pop(next_model)
        for model, dep_list in models_dict.iteritems():
            if next_model in dep_list:
                dep_list.remove(next_model)

        return next_model

    def deploy_models(self, ret):
        '''
        Method to deploy swagger file's definition objects and associated schema to AWS Apigateway as Models

        ret
            a dictionary for returning status to Saltstack
        '''

        for model, schema in self.models():
            # add in a few attributes into the model schema that AWS expects
            # _schema = schema.copy()
            _schema = self._update_schema_to_aws_notation(schema)
            _schema.update({'$schema': _Swagger.JSON_SCHEMA_DRAFT_4,
                            'title': '{0} Schema'.format(model)})

            # check to see if model already exists, aws has 2 default models [Empty, Error]
            # which may need upate with data from swagger file
            model_exists_response = __salt__['boto_apigateway.api_model_exists'](restApiId=self.restApiId,
                                                                                 modelName=model,
                                                                                 **self._common_aws_args)

            if model_exists_response.get('exists'):
                update_model_schema_response = (
                    __salt__['boto_apigateway.update_api_model_schema'](restApiId=self.restApiId,
                                                                        modelName=model,
                                                                        schema=_dict_to_json_pretty(_schema),
                                                                        **self._common_aws_args))
                if not update_model_schema_response.get('updated'):
                    ret['result'] = False
                    ret['abort'] = True
                    if 'error' in update_model_schema_response:
                        ret['comment'] = ('Failed to update existing model {0} with schema {1}, '
                                          'error: {2}'.format(model, _dict_to_json_pretty(schema),
                                                              update_model_schema_response['error']['message']))
                    return ret

                ret = _log_changes(ret, 'deploy_models', update_model_schema_response)
            else:
                create_model_response = (
                    __salt__['boto_apigateway.create_api_model'](restApiId=self.restApiId, modelName=model,
                                                                 modelDescription=model,
                                                                 schema=_dict_to_json_pretty(_schema),
                                                                 contentType='application/json',
                                                                 **self._common_aws_args))

                if not create_model_response.get('created'):
                    ret['result'] = False
                    ret['abort'] = True
                    if 'error' in create_model_response:
                        ret['comment'] = ('Failed to create model {0}, schema {1}, '
                                          'error: {2}'.format(model, _dict_to_json_pretty(schema),
                                                              create_model_response['error']['message']))
                    return ret

                ret = _log_changes(ret, 'deploy_models', create_model_response)

        return ret

    def _lambda_name(self, resourcePath, httpMethod):
        '''
        Helper method to construct lambda name based on the rule specified in doc string of
        boto_apigateway.api_present function
        '''
        lambda_name = self._lambda_funcname_format.format(stage=self._stage_name,
                                                          api=self.rest_api_name,
                                                          resource=resourcePath,
                                                          method=httpMethod)
        lambda_name = lambda_name.strip()
        lambda_name = re.sub(r'{|}', '', lambda_name)
        lambda_name = re.sub(r'\s+|/', '_', lambda_name).lower()
        return re.sub(r'_+', '_', lambda_name)

    def _lambda_uri(self, lambda_name, lambda_region):
        '''
        Helper Method to construct the lambda uri for use in method integration
        '''
        profile = self._common_aws_args.get('profile')
        region = self._common_aws_args.get('region')

        lambda_region = __utils__['boto3.get_region']('lambda', lambda_region, profile)
        apigw_region = __utils__['boto3.get_region']('apigateway', region, profile)

        lambda_desc = __salt__['boto_lambda.describe_function'](lambda_name, **self._common_aws_args)

        if lambda_region != apigw_region:
            if not lambda_desc.get('function'):
                # try look up in the same region as the apigateway as well if previous lookup failed
                lambda_desc = __salt__['boto_lambda.describe_function'](lambda_name, **self._common_aws_args)

        if not lambda_desc.get('function'):
            raise ValueError('Could not find lambda function {0} in '
                             'regions [{1}, {2}].'.format(lambda_name, lambda_region, apigw_region))

        lambda_arn = lambda_desc.get('function').get('FunctionArn')
        lambda_uri = ('arn:aws:apigateway:{0}:lambda:path/2015-03-31'
                      '/functions/{1}/invocations'.format(apigw_region, lambda_arn))
        return lambda_uri

    def _parse_method_data(self, method_name, method_data):
        '''
        Helper function to construct the method request params, models, request_templates and
        integration_type values needed to configure method request integration/mappings.
        '''
        method_params = {}
        method_models = {}
        if 'parameters' in method_data:
            for param in method_data['parameters']:
                p = _Swagger.SwaggerParameter(param)
                if p.name:
                    method_params[p.name] = True
                if p.schema:
                    method_models['application/json'] = p.schema

        request_templates = _Swagger.REQUEST_OPTION_TEMPLATE if method_name == 'options' else _Swagger.REQUEST_TEMPLATE
        integration_type = "MOCK" if method_name == 'options' else "AWS"

        return {'params': method_params,
                'models': method_models,
                'request_templates': request_templates,
                'integration_type': integration_type}

    def _find_patterns(self, o):
        result = []
        if isinstance(o, dict):
            for k, v in o.iteritems():
                if isinstance(v, dict):
                    result.extend(self._find_patterns(v))
                else:
                    if k == 'pattern':
                        result.append(v)
        return result

    def _get_pattern_for_schema(self, schema_name, httpStatus):
        '''
        returns the pattern specified in a response schema
        '''
        defaultPattern = '.+' if self._is_http_error_rescode(httpStatus) else '.*'
        model = self._models().get(schema_name)
        patterns = self._find_patterns(model)
        return patterns[0] if patterns else defaultPattern

    def _parse_method_response(self, method_name, method_response, httpStatus):
        '''
        Helper function to construct the method response params, models, and integration_params
        values needed to configure method response integration/mappings.
        '''
        method_response_models = {}
        method_response_pattern = '.*'
        if method_response.schema:
            method_response_models['application/json'] = method_response.schema
            method_response_pattern = self._get_pattern_for_schema(method_response.schema, httpStatus)

        method_response_params = {}
        method_integration_response_params = {}
        for header in method_response.headers:
            response_header = 'method.response.header.{0}'.format(header)
            method_response_params[response_header] = False
            header_data = method_response.headers.get(header)
            method_integration_response_params[response_header] = (
                "'{0}'".format(header_data.get('default')) if 'default' in header_data else "'*'")

        if method_name == 'options' or not self._is_http_error_rescode(httpStatus):
            response_templates = _Swagger.RESPONSE_OPTION_TEMPLATE
        else:
            response_templates = _Swagger.RESPONSE_TEMPLATE

        return {'params': method_response_params,
                'models': method_response_models,
                'integration_params': method_integration_response_params,
                'pattern': method_response_pattern,
                'response_templates': response_templates}

    def _deploy_method(self, ret, resource_path, method_name, method_data, api_key_required,
                       lambda_integration_role, lambda_region, authorization_type):
        '''
        Method to create a method for the given resource path, along with its associated
        request and response integrations.

        ret
            a dictionary for returning status to Saltstack

        resource_path
            the full resource path where the named method_name will be associated with.

        method_name
            a string that is one of the following values: 'delete', 'get', 'head', 'options',
            'patch', 'post', 'put'

        method_data
            the value dictionary for this method in the swagger definition file.

        api_key_required
            True or False, whether api key is required to access this method.

        lambda_integration_role
            name of the IAM role or IAM role arn that Api Gateway will assume when executing
            the associated lambda function

        lambda_region
            the region for the lambda function that Api Gateway will integrate to.

        authorization_type
            'NONE' or 'AWS_IAM'

        '''
        method = self._parse_method_data(method_name.lower(), method_data)

        # authorizationType is hard coded to 'NONE' for now.
        m = __salt__['boto_apigateway.create_api_method'](restApiId=self.restApiId,
                                                          resourcePath=resource_path,
                                                          httpMethod=method_name.upper(),
                                                          authorizationType=authorization_type,
                                                          apiKeyRequired=api_key_required,
                                                          requestParameters=method.get('params'),
                                                          requestModels=method.get('models'),
                                                          **self._common_aws_args)
        if not m.get('created'):
            ret = _log_error_and_abort(ret, m)
            return ret

        ret = _log_changes(ret, '_deploy_method.create_api_method', m)

        lambda_uri = ""
        if method_name.lower() != 'options':
            lambda_uri = self._lambda_uri(self._lambda_name(resource_path, method_name),
                                          lambda_region=lambda_region)

        # NOTE: integration method is set to POST always, as otherwise AWS makes wrong assumptions
        # about the intent of the call. HTTP method will be passed to lambda as part of the API gateway context
        integration = (
            __salt__['boto_apigateway.create_api_integration'](restApiId=self.restApiId,
                                                               resourcePath=resource_path,
                                                               httpMethod=method_name.upper(),
                                                               integrationType=method.get('integration_type'),
                                                               integrationHttpMethod='POST',
                                                               uri=lambda_uri,
                                                               credentials=lambda_integration_role,
                                                               requestTemplates=method.get('request_templates'),
                                                               **self._common_aws_args))
        if not integration.get('created'):
            ret = _log_error_and_abort(ret, integration)
            return ret
        ret = _log_changes(ret, '_deploy_method.create_api_integration', integration)

        if 'responses' in method_data:
            for response, response_data in method_data['responses'].iteritems():
                httpStatus = str(response)
                method_response = self._parse_method_response(method_name.lower(),
                                                              _Swagger.SwaggerMethodResponse(response_data), httpStatus)

                mr = __salt__['boto_apigateway.create_api_method_response'](
                                                                restApiId=self.restApiId,
                                                                resourcePath=resource_path,
                                                                httpMethod=method_name.upper(),
                                                                statusCode=httpStatus,
                                                                responseParameters=method_response.get('params'),
                                                                responseModels=method_response.get('models'),
                                                                **self._common_aws_args)
                if not mr.get('created'):
                    ret = _log_error_and_abort(ret, mr)
                    return ret
                ret = _log_changes(ret, '_deploy_method.create_api_method_response', mr)

                mir = __salt__['boto_apigateway.create_api_integration_response'](
                                                restApiId=self.restApiId,
                                                resourcePath=resource_path,
                                                httpMethod=method_name.upper(),
                                                statusCode=httpStatus,
                                                selectionPattern=method_response.get('pattern'),
                                                responseParameters=method_response.get('integration_params'),
                                                responseTemplates=method_response.get('response_templates'),
                                                **self._common_aws_args)
                if not mir.get('created'):
                    ret = _log_error_and_abort(ret, mir)
                    return ret
                ret = _log_changes(ret, '_deploy_method.create_api_integration_response', mir)
        else:
            raise ValueError('No responses specified for {0} {1}'.format(resource_path, method_name))

        return ret

    def deploy_resources(self, ret, api_key_required, lambda_integration_role, lambda_region, authorization_type):
        '''
        Method to deploy resources defined in the swagger file.

        ret
            a dictionary for returning status to Saltstack

        api_key_required
            True or False, whether api key is required to access this method.

        lambda_integration_role
            name of the IAM role or IAM role arn that Api Gateway will assume when executing
            the associated lambda function

        lambda_region
            the region for the lambda function that Api Gateway will integrate to.

        authorization_type
            'NONE' or 'AWS_IAM'
        '''

        for path, pathData in self.paths:
            resource = __salt__['boto_apigateway.create_api_resources'](restApiId=self.restApiId,
                                                                        path=path,
                                                                        **self._common_aws_args)
            if not resource.get('created'):
                ret = _log_error_and_abort(ret, resource)
                return ret
            ret = _log_changes(ret, 'deploy_resources', resource)
            for method, method_data in pathData.iteritems():
                if method in _Swagger.SWAGGER_OPERATION_NAMES:
                    ret = self._deploy_method(ret, path, method, method_data, api_key_required,
                                              lambda_integration_role, lambda_region, authorization_type)
        return ret

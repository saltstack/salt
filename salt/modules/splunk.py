"""
Module for interop with the Splunk API

.. versionadded:: 2016.3.0


:depends:   - splunk-sdk python module
:configuration: Configure this module by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config. The module
    will use the 'splunk' key by default, if defined.

    For example:

    .. code-block:: yaml

        splunk:
            username: alice
            password: abc123
            host: example.splunkcloud.com
            port: 8080
"""

import base64
import hmac
import logging
import subprocess

HAS_LIBS = False
try:
    import splunklib.client
    from splunklib.binding import HTTPError
    from splunklib.client import AuthenticationError

    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = "splunk"

SERVICE_NAME = "splunk"

ALLOWED_FIELDS_FOR_MODIFICATION = [
    "realname",
    "roles",
    "defaultApp",
    "tz",
    #'capabilities',
    "name",
]

REQUIRED_FIELDS_FOR_CREATE = ["realname", "name", "roles"]


def __virtual__():
    """
    Only load this module if splunk is installed on this minion.
    """
    if HAS_LIBS:
        return __virtualname__
    return (
        False,
        "The splunk execution module failed to load: "
        "requires splunk python library to be installed.",
    )


def _get_secret_key(profile):
    config = __salt__["config.option"](profile)
    return config.get("password_secret_key")


def _generate_password(email):
    m = hmac.new(
        base64.b64decode(_get_secret_key("splunk")),
        str([email, SERVICE_NAME]),
    )
    return base64.urlsafe_b64encode(m.digest()).strip().replace("=", "")


def _send_email(name, email):
    "send a email to inform user of account creation"
    config = __salt__["config.option"]("splunk")
    email_object = config.get("email")
    if email_object:
        cc = email_object.get("cc")
        subject = email_object.get("subject")
        message = email_object.get("message").format(
            name, name, _generate_password(email), name
        )

        try:
            mail_process = subprocess.Popen(
                ["mail", "-s", subject, "-c", cc, email], stdin=subprocess.PIPE
            )
        except Exception as e:  # pylint: disable=broad-except
            log.error("unable to send email to %s: %s", email, e)

        mail_process.communicate(message)

        log.info("sent account creation email to %s", email)


def _populate_cache(profile="splunk"):
    config = __salt__["config.option"](profile)

    key = "splunk.users.{}".format(config.get("host"))

    if key not in __context__:
        client = _get_splunk(profile)
        kwargs = {"sort_key": "realname", "sort_dir": "asc"}
        users = client.users.list(count=-1, **kwargs)

        result = {}
        for user in users:
            result[user.email.lower()] = user

        __context__[key] = result

    return True


def _get_splunk(profile):
    """
    Return the splunk client, cached into __context__ for performance
    """
    config = __salt__["config.option"](profile)

    key = "splunk.{}:{}:{}:{}".format(
        config.get("host"),
        config.get("port"),
        config.get("username"),
        config.get("password"),
    )

    if key not in __context__:
        __context__[key] = splunklib.client.connect(
            host=config.get("host"),
            port=config.get("port"),
            username=config.get("username"),
            password=config.get("password"),
        )

    return __context__[key]


def list_users(profile="splunk"):
    """
    List all users in the splunk DB

    CLI Example:

    .. code-block:: bash

        salt myminion splunk.list_users
    """

    config = __salt__["config.option"](profile)
    key = "splunk.users.{}".format(config.get("host"))

    if key not in __context__:
        _populate_cache(profile)

    return __context__[key]


def get_user(email, profile="splunk", **kwargs):
    """
    Get a splunk user by name/email

    CLI Example:

    .. code-block:: bash

        salt myminion splunk.get_user 'user@example.com' user_details=false
        salt myminion splunk.get_user 'user@example.com' user_details=true
    """

    user_map = list_users(profile)
    user_found = email.lower() in user_map.keys()

    if not kwargs.get("user_details", False) and user_found:
        # The user is in splunk group, just return
        return True
    elif kwargs.get("user_details", False) and user_found:
        user = user_map[email.lower()]

        response = {}
        for field in ["defaultApp", "realname", "name", "email"]:
            response[field] = user[field]

        response["roles"] = []
        for role in user.role_entities:
            response["roles"].append(role.name)

        return response

    return False


def create_user(email, profile="splunk", **kwargs):
    """
    create a splunk user by name/email

    CLI Example:

    .. code-block:: bash

        salt myminion splunk.create_user user@example.com roles=['user'] realname="Test User" name=testuser
    """

    client = _get_splunk(profile)

    email = email.lower()

    user = list_users(profile).get(email)

    if user:
        log.error("User is already present %s", email)
        return False

    property_map = {}

    for field in ALLOWED_FIELDS_FOR_MODIFICATION:
        if kwargs.get(field):
            property_map[field] = kwargs.get(field)

    try:
        # create
        for req_field in REQUIRED_FIELDS_FOR_CREATE:
            if not property_map.get(req_field):
                log.error(
                    "Missing required params %s",
                    ", ".join([str(k) for k in REQUIRED_FIELDS_FOR_CREATE]),
                )
                return False

        newuser = client.users.create(
            username=property_map["name"],
            password=_generate_password(email),
            roles=property_map["roles"],
            email=email,
            realname=property_map["realname"],
        )

        _send_email(newuser.name, newuser.email)

        response = {}
        for field in ["email", "password", "realname", "roles"]:
            response[field] = newuser[field]

    except Exception as e:  # pylint: disable=broad-except
        log.error("Caught exception %s", e)
        return False


def update_user(email, profile="splunk", **kwargs):
    """
    Create a splunk user by email

    CLI Example:

    .. code-block:: bash

        salt myminion splunk.update_user example@domain.com roles=['user'] realname="Test User"
    """

    client = _get_splunk(profile)

    email = email.lower()

    user = list_users(profile).get(email)

    if not user:
        log.error("Failed to retrieve user %s", email)
        return False

    property_map = {}

    for field in ALLOWED_FIELDS_FOR_MODIFICATION:
        if kwargs.get(field):
            property_map[field] = kwargs.get(field)

    # update
    kwargs = {}
    roles = [role.name for role in user.role_entities]

    for k, v in property_map.items():
        resource_value = user[k]
        if resource_value is not None:
            # you can't update the username in update api call
            if k.lower() == "name":
                continue
            if k.lower() == "roles":
                if isinstance(v, str):
                    v = v.split(",")
                if set(roles) != set(v):
                    kwargs["roles"] = list(set(v))
            elif resource_value != v:
                kwargs[k] = v

    if kwargs:
        user.update(**kwargs).refresh()

        fields_modified = {}
        for field in ALLOWED_FIELDS_FOR_MODIFICATION:
            fields_modified[field] = user[field]

    else:
        # succeeded, no change
        return True


def delete_user(email, profile="splunk"):
    """
    Delete a splunk user by email

    CLI Example:

    .. code-block:: bash

        salt myminion splunk_user.delete 'user@example.com'
    """

    client = _get_splunk(profile)

    user = list_users(profile).get(email)

    if user:
        try:
            client.users.delete(user.name)
        except (AuthenticationError, HTTPError) as e:
            log.info("Exception: %s", e)
            return False
    else:
        return False

    return user.name not in client.users

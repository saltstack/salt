"""
JIRA Execution module
=====================

.. versionadded:: 2019.2.0

Execution module to manipulate JIRA tickets via Salt.

This module requires the ``jira`` Python library to be installed.

Configuration example:

.. code-block:: yaml

  jira:
    server: https://jira.atlassian.org
    username: salt
    password: pass
"""

import logging

import salt.utils.args

try:
    import jira

    HAS_JIRA = True
except ImportError:
    HAS_JIRA = False

log = logging.getLogger(__name__)

__virtualname__ = "jira"
__proxyenabled__ = ["*"]

JIRA = None


def __virtual__():
    return (
        __virtualname__
        if HAS_JIRA
        else (False, "Please install the jira Python library from PyPI")
    )


def _get_credentials(server=None, username=None, password=None):
    """
    Returns the credentials merged with the config data (opts + pillar).
    """
    jira_cfg = __salt__["config.merge"]("jira", default={})
    if not server:
        server = jira_cfg.get("server")
    if not username:
        username = jira_cfg.get("username")
    if not password:
        password = jira_cfg.get("password")
    return server, username, password


def _get_jira(server=None, username=None, password=None):
    global JIRA
    if not JIRA:
        server, username, password = _get_credentials(
            server=server, username=username, password=password
        )
        JIRA = jira.JIRA(
            basic_auth=(username, password), server=server, logging=True
        )  # We want logging
    return JIRA


def create_issue(
    project,
    summary,
    description,
    template_engine="jinja",
    context=None,
    defaults=None,
    saltenv="base",
    issuetype="Bug",
    priority="Normal",
    labels=None,
    assignee=None,
    server=None,
    username=None,
    password=None,
    **kwargs
):
    """
    Create a JIRA issue using the named settings. Return the JIRA ticket ID.

    project
        The name of the project to attach the JIRA ticket to.

    summary
        The summary (title) of the JIRA ticket. When the ``template_engine``
        argument is set to a proper value of an existing Salt template engine
        (e.g., ``jinja``, ``mako``, etc.) it will render the ``summary`` before
        creating the ticket.

    description
        The full body description of the JIRA ticket. When the ``template_engine``
        argument is set to a proper value of an existing Salt template engine
        (e.g., ``jinja``, ``mako``, etc.) it will render the ``description`` before
        creating the ticket.

    template_engine: ``jinja``
        The name of the template engine to be used to render the values of the
        ``summary`` and ``description`` arguments. Default: ``jinja``.

    context: ``None``
        The context to pass when rendering the ``summary`` and ``description``.
        This argument is ignored when ``template_engine`` is set as ``None``

    defaults: ``None``
        Default values to pass to the Salt rendering pipeline for the
        ``summary`` and ``description`` arguments.
        This argument is ignored when ``template_engine`` is set as ``None``.

    saltenv: ``base``
        The Salt environment name (for the rendering system).

    issuetype: ``Bug``
        The type of the JIRA ticket. Default: ``Bug``.

    priority: ``Normal``
        The priority of the JIRA ticket. Default: ``Normal``.

    labels: ``None``
        A list of labels to add to the ticket.

    assignee: ``None``
        The name of the person to assign the ticket to.

    CLI Examples:

    .. code-block:: bash

        salt '*' jira.create_issue NET 'Ticket title' 'Ticket description'
        salt '*' jira.create_issue NET 'Issue on {{ opts.id }}' 'Error detected on {{ opts.id }}' template_engine=jinja
    """
    if template_engine:
        summary = __salt__["file.apply_template_on_contents"](
            summary,
            template=template_engine,
            context=context,
            defaults=defaults,
            saltenv=saltenv,
        )
        description = __salt__["file.apply_template_on_contents"](
            description,
            template=template_engine,
            context=context,
            defaults=defaults,
            saltenv=saltenv,
        )
    jira_ = _get_jira(server=server, username=username, password=password)
    if not labels:
        labels = []
    data = {
        "project": {"key": project},
        "summary": summary,
        "description": description,
        "issuetype": {"name": issuetype},
        "priority": {"name": priority},
        "labels": labels,
    }
    data.update(salt.utils.args.clean_kwargs(**kwargs))
    issue = jira_.create_issue(data)
    issue_key = str(issue)
    if assignee:
        assign_issue(issue_key, assignee)
    return issue_key


def assign_issue(issue_key, assignee, server=None, username=None, password=None):
    """
    Assign the issue to an existing user. Return ``True`` when the issue has
    been properly assigned.

    issue_key
        The JIRA ID of the ticket to manipulate.

    assignee
        The name of the user to assign the ticket to.

    CLI Example:

    .. code-block:: bash

        salt '*' jira.assign_issue NET-123 example_user
    """
    jira_ = _get_jira(server=server, username=username, password=password)
    assigned = jira_.assign_issue(issue_key, assignee)
    return assigned


def add_comment(
    issue_key,
    comment,
    visibility=None,
    is_internal=False,
    server=None,
    username=None,
    password=None,
):
    """
    Add a comment to an existing ticket. Return ``True`` when it successfully
    added the comment.

    issue_key
        The issue ID to add the comment to.

    comment
        The body of the comment to be added.

    visibility: ``None``
        A dictionary having two keys:

        - ``type``: is ``role`` (or ``group`` if the JIRA server has configured
          comment visibility for groups).
        - ``value``: the name of the role (or group) to which viewing of this
          comment will be restricted.

    is_internal: ``False``
        Whether a comment has to be marked as ``Internal`` in Jira Service Desk.

    CLI Example:

    .. code-block:: bash

        salt '*' jira.add_comment NE-123 'This is a comment'
    """
    jira_ = _get_jira(server=server, username=username, password=password)
    comm = jira_.add_comment(
        issue_key, comment, visibility=visibility, is_internal=is_internal
    )
    return True


def issue_closed(issue_key, server=None, username=None, password=None):
    """
    Check if the issue is closed.

    issue_key
        The JIRA iD of the ticket to close.

    Returns:

    - ``True``: the ticket exists and it is closed.
    - ``False``: the ticket exists and it has not been closed.
    - ``None``: the ticket does not exist.

    CLI Example:

    .. code-block:: bash

        salt '*' jira.issue_closed NE-123
    """
    if not issue_key:
        return None
    jira_ = _get_jira(server=server, username=username, password=password)
    try:
        ticket = jira_.issue(issue_key)
    except jira.exceptions.JIRAError:
        # Ticket not found
        return None
    return ticket.fields().status.name == "Closed"

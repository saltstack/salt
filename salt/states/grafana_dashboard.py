"""
Manage Grafana v2.0 Dashboards

.. versionadded:: 2016.3.0

.. code-block:: yaml

    grafana:
      grafana_timeout: 3
      grafana_token: qwertyuiop
      grafana_url: 'https://url.com'

.. code-block:: yaml

    Ensure minimum dashboard is managed:
      grafana_dashboard.present:
        - name: insightful-dashboard
        - base_dashboards_from_pillar:
          - default_dashboard
        - base_rows_from_pillar:
          - default_row
        - base_panels_from_pillar:
          - default_panel
        - dashboard:
            rows:
              - title: Usage
                panels:
                  - targets:
                      - target: alias(constantLine(50), 'max')
                    title: Imaginary
                    type: graph


The behavior of this module is to create dashboards if they do not exist, to
add rows if they do not exist in existing dashboards, and to update rows if
they exist in dashboards. The module will not manage rows that are not defined,
allowing users to manage their own custom rows.
"""

import copy

import requests

import salt.utils.json
from salt.utils.dictdiffer import DictDiffer


def __virtual__():
    """
    Only load if grafana v2.0 is configured.
    """
    if __salt__["config.get"]("grafana_version", 1) == 2:
        return True
    return (False, "Not configured for grafana_version 2")


_DEFAULT_DASHBOARD_PILLAR = "grafana_dashboards:default"
_DEFAULT_PANEL_PILLAR = "grafana_panels:default"
_DEFAULT_ROW_PILLAR = "grafana_rows:default"
_PINNED_ROWS_PILLAR = "grafana_pinned_rows"


def present(
    name,
    base_dashboards_from_pillar=None,
    base_panels_from_pillar=None,
    base_rows_from_pillar=None,
    dashboard=None,
    profile="grafana",
):
    """
    Ensure the grafana dashboard exists and is managed.

    name
        Name of the grafana dashboard.

    base_dashboards_from_pillar
        A pillar key that contains a list of dashboards to inherit from

    base_panels_from_pillar
        A pillar key that contains a list of panels to inherit from

    base_rows_from_pillar
        A pillar key that contains a list of rows to inherit from

    dashboard
        A dict that defines a dashboard that should be managed.

    profile
        A pillar key or dict that contains grafana information
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    base_dashboards_from_pillar = base_dashboards_from_pillar or []
    base_panels_from_pillar = base_panels_from_pillar or []
    base_rows_from_pillar = base_rows_from_pillar or []
    dashboard = dashboard or {}

    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)

    # Add pillar keys for default configuration
    base_dashboards_from_pillar = [
        _DEFAULT_DASHBOARD_PILLAR
    ] + base_dashboards_from_pillar
    base_panels_from_pillar = [_DEFAULT_PANEL_PILLAR] + base_panels_from_pillar
    base_rows_from_pillar = [_DEFAULT_ROW_PILLAR] + base_rows_from_pillar

    # Build out all dashboard fields
    new_dashboard = _inherited_dashboard(dashboard, base_dashboards_from_pillar, ret)
    new_dashboard["title"] = name
    rows = new_dashboard.get("rows", [])
    for i, row in enumerate(rows):
        rows[i] = _inherited_row(row, base_rows_from_pillar, ret)
    for row in rows:
        panels = row.get("panels", [])
        for i, panel in enumerate(panels):
            panels[i] = _inherited_panel(panel, base_panels_from_pillar, ret)
    _auto_adjust_panel_spans(new_dashboard)
    _ensure_panel_ids(new_dashboard)
    _ensure_annotations(new_dashboard)

    # Create dashboard if it does not exist
    url = f"db/{name}"
    old_dashboard = _get(url, profile)
    if not old_dashboard:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Dashboard {name} is set to be created."
            return ret

        response = _update(new_dashboard, profile)
        if response.get("status") == "success":
            ret["comment"] = f"Dashboard {name} created."
            ret["changes"]["new"] = f"Dashboard {name} created."
        else:
            ret["result"] = False
            ret["comment"] = "Failed to create dashboard {}, response={}".format(
                name, response
            )
        return ret

    # Add unmanaged rows to the dashboard. They appear at the top if they are
    # marked as pinned. They appear at the bottom otherwise.
    managed_row_titles = [row.get("title") for row in new_dashboard.get("rows", [])]
    new_rows = new_dashboard.get("rows", [])
    for old_row in old_dashboard.get("rows", []):
        if old_row.get("title") not in managed_row_titles:
            new_rows.append(copy.deepcopy(old_row))
    _ensure_pinned_rows(new_dashboard)
    _ensure_panel_ids(new_dashboard)

    # Update dashboard if it differs
    dashboard_diff = DictDiffer(_cleaned(new_dashboard), _cleaned(old_dashboard))
    updated_needed = (
        dashboard_diff.changed() or dashboard_diff.added() or dashboard_diff.removed()
    )
    if updated_needed:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Dashboard {} is set to be updated, changes={}".format(
                name,
                salt.utils.json.dumps(
                    _dashboard_diff(_cleaned(new_dashboard), _cleaned(old_dashboard)),
                    indent=4,
                ),
            )
            return ret

        response = _update(new_dashboard, profile)
        if response.get("status") == "success":
            updated_dashboard = _get(url, profile)
            dashboard_diff = DictDiffer(
                _cleaned(updated_dashboard), _cleaned(old_dashboard)
            )
            ret["comment"] = f"Dashboard {name} updated."
            ret["changes"] = _dashboard_diff(
                _cleaned(new_dashboard), _cleaned(old_dashboard)
            )
        else:
            ret["result"] = False
            ret["comment"] = "Failed to update dashboard {}, response={}".format(
                name, response
            )
        return ret

    ret["comment"] = "Dashboard present"
    return ret


def absent(name, profile="grafana"):
    """
    Ensure the named grafana dashboard is absent.

    name
        Name of the grafana dashboard.

    profile
        A pillar key or dict that contains grafana information
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if isinstance(profile, str):
        profile = __salt__["config.option"](profile)

    url = f"db/{name}"
    existing_dashboard = _get(url, profile)
    if existing_dashboard:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Dashboard {name} is set to be deleted."
            return ret

        _delete(url, profile)
        ret["comment"] = f"Dashboard {name} deleted."
        ret["changes"]["new"] = f"Dashboard {name} deleted."
        return ret

    ret["comment"] = "Dashboard absent"
    return ret


_IGNORED_DASHBOARD_FIELDS = [
    "id",
    "originalTitle",
    "version",
]
_IGNORED_ROW_FIELDS = []
_IGNORED_PANEL_FIELDS = [
    "grid",
    "mode",
    "tooltip",
]
_IGNORED_TARGET_FIELDS = [
    "textEditor",
]


def _cleaned(_dashboard):
    """Return a copy without fields that can differ."""
    dashboard = copy.deepcopy(_dashboard)

    for ignored_dashboard_field in _IGNORED_DASHBOARD_FIELDS:
        dashboard.pop(ignored_dashboard_field, None)
    for row in dashboard.get("rows", []):
        for ignored_row_field in _IGNORED_ROW_FIELDS:
            row.pop(ignored_row_field, None)
        for i, panel in enumerate(row.get("panels", [])):
            for ignored_panel_field in _IGNORED_PANEL_FIELDS:
                panel.pop(ignored_panel_field, None)
            for target in panel.get("targets", []):
                for ignored_target_field in _IGNORED_TARGET_FIELDS:
                    target.pop(ignored_target_field, None)
            row["panels"][i] = _stripped(panel)

    return dashboard


def _inherited_dashboard(dashboard, base_dashboards_from_pillar, ret):
    """Return a dashboard with properties from parents."""
    base_dashboards = []
    for base_dashboard_from_pillar in base_dashboards_from_pillar:
        base_dashboard = __salt__["pillar.get"](base_dashboard_from_pillar)
        if base_dashboard:
            base_dashboards.append(base_dashboard)
        elif base_dashboard_from_pillar != _DEFAULT_DASHBOARD_PILLAR:
            ret.setdefault("warnings", [])
            warning_message = 'Cannot find dashboard pillar "{}".'.format(
                base_dashboard_from_pillar
            )
            if warning_message not in ret["warnings"]:
                ret["warnings"].append(warning_message)
    base_dashboards.append(dashboard)

    result_dashboard = {}
    tags = set()
    for dashboard in base_dashboards:
        tags.update(dashboard.get("tags", []))
        result_dashboard.update(dashboard)
    result_dashboard["tags"] = list(tags)
    return result_dashboard


def _inherited_row(row, base_rows_from_pillar, ret):
    """Return a row with properties from parents."""
    base_rows = []
    for base_row_from_pillar in base_rows_from_pillar:
        base_row = __salt__["pillar.get"](base_row_from_pillar)
        if base_row:
            base_rows.append(base_row)
        elif base_row_from_pillar != _DEFAULT_ROW_PILLAR:
            ret.setdefault("warnings", [])
            warning_message = 'Cannot find row pillar "{}".'.format(
                base_row_from_pillar
            )
            if warning_message not in ret["warnings"]:
                ret["warnings"].append(warning_message)
    base_rows.append(row)

    result_row = {}
    for row in base_rows:
        result_row.update(row)
    return result_row


def _inherited_panel(panel, base_panels_from_pillar, ret):
    """Return a panel with properties from parents."""
    base_panels = []
    for base_panel_from_pillar in base_panels_from_pillar:
        base_panel = __salt__["pillar.get"](base_panel_from_pillar)
        if base_panel:
            base_panels.append(base_panel)
        elif base_panel_from_pillar != _DEFAULT_PANEL_PILLAR:
            ret.setdefault("warnings", [])
            warning_message = 'Cannot find panel pillar "{}".'.format(
                base_panel_from_pillar
            )
            if warning_message not in ret["warnings"]:
                ret["warnings"].append(warning_message)
    base_panels.append(panel)

    result_panel = {}
    for panel in base_panels:
        result_panel.update(panel)
    return result_panel


_FULL_LEVEL_SPAN = 12
_DEFAULT_PANEL_SPAN = 2.5


def _auto_adjust_panel_spans(dashboard):
    """Adjust panel spans to take up the available width.

    For each group of panels that would be laid out on the same level, scale up
    the unspecified panel spans to fill up the level.
    """
    for row in dashboard.get("rows", []):
        levels = []
        current_level = []
        levels.append(current_level)
        for panel in row.get("panels", []):
            current_level_span = sum(
                panel.get("span", _DEFAULT_PANEL_SPAN) for panel in current_level
            )
            span = panel.get("span", _DEFAULT_PANEL_SPAN)
            if current_level_span + span > _FULL_LEVEL_SPAN:
                current_level = [panel]
                levels.append(current_level)
            else:
                current_level.append(panel)

        for level in levels:
            specified_panels = [panel for panel in level if "span" in panel]
            unspecified_panels = [panel for panel in level if "span" not in panel]
            if not unspecified_panels:
                continue

            specified_span = sum(panel["span"] for panel in specified_panels)
            available_span = _FULL_LEVEL_SPAN - specified_span
            auto_span = float(available_span) / len(unspecified_panels)
            for panel in unspecified_panels:
                panel["span"] = auto_span


def _ensure_pinned_rows(dashboard):
    """Pin rows to the top of the dashboard."""
    pinned_row_titles = __salt__["pillar.get"](_PINNED_ROWS_PILLAR)
    if not pinned_row_titles:
        return

    pinned_row_titles_lower = []
    for title in pinned_row_titles:
        pinned_row_titles_lower.append(title.lower())
    rows = dashboard.get("rows", [])
    pinned_rows = []
    for i, row in enumerate(rows):
        if row.get("title", "").lower() in pinned_row_titles_lower:
            del rows[i]
            pinned_rows.append(row)
    rows = pinned_rows + rows


def _ensure_panel_ids(dashboard):
    """Assign panels auto-incrementing IDs."""
    panel_id = 1
    for row in dashboard.get("rows", []):
        for panel in row.get("panels", []):
            panel["id"] = panel_id
            panel_id += 1


def _ensure_annotations(dashboard):
    """Explode annotation_tags into annotations."""
    if "annotation_tags" not in dashboard:
        return
    tags = dashboard["annotation_tags"]
    annotations = {
        "enable": True,
        "list": [],
    }
    for tag in tags:
        annotations["list"].append(
            {
                "datasource": "graphite",
                "enable": False,
                "iconColor": "#C0C6BE",
                "iconSize": 13,
                "lineColor": "rgba(255, 96, 96, 0.592157)",
                "name": tag,
                "showLine": True,
                "tags": tag,
            }
        )
    del dashboard["annotation_tags"]
    dashboard["annotations"] = annotations


def _get(url, profile):
    """Get a specific dashboard."""
    request_url = "{}/api/dashboards/{}".format(profile.get("grafana_url"), url)
    response = requests.get(
        request_url,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(profile.get("grafana_token")),
        },
        timeout=profile.get("grafana_timeout", 3),
    )
    data = response.json()
    if data.get("message") == "Not found":
        return None
    if "dashboard" not in data:
        return None
    return data["dashboard"]


def _delete(url, profile):
    """Delete a specific dashboard."""
    request_url = "{}/api/dashboards/{}".format(profile.get("grafana_url"), url)
    response = requests.delete(
        request_url,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(profile.get("grafana_token")),
        },
        timeout=profile.get("grafana_timeout"),
    )
    data = response.json()
    return data


def _update(dashboard, profile):
    """Update a specific dashboard."""
    payload = {"dashboard": dashboard, "overwrite": True}
    request_url = "{}/api/dashboards/db".format(profile.get("grafana_url"))
    response = requests.post(
        request_url,
        headers={"Authorization": "Bearer {}".format(profile.get("grafana_token"))},
        json=payload,
        timeout=120,
    )
    return response.json()


def _dashboard_diff(_new_dashboard, _old_dashboard):
    """Return a dictionary of changes between dashboards."""
    diff = {}

    # Dashboard diff
    new_dashboard = copy.deepcopy(_new_dashboard)
    old_dashboard = copy.deepcopy(_old_dashboard)
    dashboard_diff = DictDiffer(new_dashboard, old_dashboard)
    diff["dashboard"] = _stripped(
        {
            "changed": list(dashboard_diff.changed()) or None,
            "added": list(dashboard_diff.added()) or None,
            "removed": list(dashboard_diff.removed()) or None,
        }
    )

    # Row diff
    new_rows = new_dashboard.get("rows", [])
    old_rows = old_dashboard.get("rows", [])
    new_rows_by_title = {}
    old_rows_by_title = {}
    for row in new_rows:
        if "title" in row:
            new_rows_by_title[row["title"]] = row
    for row in old_rows:
        if "title" in row:
            old_rows_by_title[row["title"]] = row
    rows_diff = DictDiffer(new_rows_by_title, old_rows_by_title)
    diff["rows"] = _stripped(
        {
            "added": list(rows_diff.added()) or None,
            "removed": list(rows_diff.removed()) or None,
        }
    )
    for changed_row_title in rows_diff.changed():
        old_row = old_rows_by_title[changed_row_title]
        new_row = new_rows_by_title[changed_row_title]
        row_diff = DictDiffer(new_row, old_row)
        diff["rows"].setdefault("changed", {})
        diff["rows"]["changed"][changed_row_title] = _stripped(
            {
                "changed": list(row_diff.changed()) or None,
                "added": list(row_diff.added()) or None,
                "removed": list(row_diff.removed()) or None,
            }
        )

    # Panel diff
    old_panels_by_id = {}
    new_panels_by_id = {}
    for row in old_dashboard.get("rows", []):
        for panel in row.get("panels", []):
            if "id" in panel:
                old_panels_by_id[panel["id"]] = panel
    for row in new_dashboard.get("rows", []):
        for panel in row.get("panels", []):
            if "id" in panel:
                new_panels_by_id[panel["id"]] = panel
    panels_diff = DictDiffer(new_panels_by_id, old_panels_by_id)
    diff["panels"] = _stripped(
        {
            "added": list(panels_diff.added()) or None,
            "removed": list(panels_diff.removed()) or None,
        }
    )
    for changed_panel_id in panels_diff.changed():
        old_panel = old_panels_by_id[changed_panel_id]
        new_panel = new_panels_by_id[changed_panel_id]
        panels_diff = DictDiffer(new_panel, old_panel)
        diff["panels"].setdefault("changed", {})
        diff["panels"]["changed"][changed_panel_id] = _stripped(
            {
                "changed": list(panels_diff.changed()) or None,
                "added": list(panels_diff.added()) or None,
                "removed": list(panels_diff.removed()) or None,
            }
        )

    return diff


def _stripped(d):
    """Strip falsey entries."""
    ret = {}
    for k, v in d.items():
        if v:
            ret[k] = v
    return ret

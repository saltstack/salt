# -*- coding: utf-8 -*-
'''
Manage Grafana Dashboards

This module uses ``elasticsearch``, which can be installed via package, or pip.

You can specify elasticsearch hosts directly to the module, or you can use an
elasticsearch profile via pillars:

.. code-block:: yaml

    mygrafanaprofile:
      hosts:
        - es1.example.com:9200
        - es2.example.com:9200
      index: grafana-dash

.. code-block:: yaml

    # Basic usage (uses default pillar profile key 'grafana')
    Ensure myservice dashboard is managed:
      grafana.dashboard_present:
        - name: myservice
        - dashboard_from_pillar: default
        - rows_from_pillar:
            - systemhealth
            - requests

    # Passing hosts in
    Ensure myservice dashboard is managed:
      grafana.dashboard_present:
        - name: myservice
        - dashboard_from_pillar: default
        - rows:
            - collapse: false
              editable: true
              height: 150px
              title: System Health
              panels:
                - aliasColors: {}
                  id: 200000
                  annotate:
                    enable: false
                  bars: false
                  datasource: null
                  editable: true
                  error: false
                  fill: 7
                  grid:
                    leftMax: 100
                    leftMin: null
                    rightMax: null
                    rightMin: null
                    threshold1: 60
                    threshold1Color: rgb(216, 27, 27)
                    threshold2: null
                    threshold2Color: rgba(234, 112, 112, 0.22)
                  leftYAxisLabel: ''
                  legend:
                    avg: false
                    current: false
                    max: false
                    min: false
                    show: false
                    total: false
                    values: false
                  lines: true
                  linewidth: 1
                  nullPointMode: connected
                  percentage: false
                  pointradius: 5
                  points: false
                  renderer: flot
                  resolution: 100
                  scale: 1
                  seriesOverrides: []
                  span: 4
                  stack: false
                  steppedLine: false
                  targets:
                    - target: cloudwatch.aws.ec2.mysrv.cpuutilization.average
                  title: CPU (asg average)
                  tooltip:
                    query_as_alias: true
                    shared: false
                    value_type: cumulative
                  type: graph
                  x-axis: true
                  y-axis: true
                  y_formats:
                    - short
                    - short
                  zerofill: true
        - rows_from_pillar:
          - systemhealth
          - requests
        - profile:
            hosts:
              - es1.example.com:9200
              - es2.example.com:9200
            index: grafana-dash

    # Using a profile from pillars
    Ensure myservice dashboard is managed:
      grafana.dashboard_present:
        - name: myservice
        - dashboard:
            annotations:
              enable: true
              list: []
            editable: true
            hideAllLegends: false
            hideControls: false
            nav:
              - collapse: false
                enable: true
                notice: false
                now: true
                refresh_intervals:
                  - 10s
                  - 30s
                  - 1m
                  - 5m
                  - 15m
                  - 30m
                  - 1h
                  - 2h
                  - 1d
                status: Stable
                time_options:
                  - 5m
                  - 15m
                  - 1h
                  - 2h
                  - 3h
                  - 4h
                  - 6h
                  - 12h
                  - 1d
                  - 2d
                  - 4d
                  - 7d
                  - 16d
                  - 30d
                type: timepicker
            originalTitle: dockerregistry
            refresh: 1m
            rows: []
            sharedCrosshair: false
            style: dark
            tags: []
            templating:
              enable: true
              list: []
            time:
              from: now-2h
              to: now
            timezone: browser
        - rows_from_pillars:
          - systemhealth
          - requests
        - profile: mygrafanaprofile

The behavior of this module is to create dashboards if they do not exist, to
add rows if they do not exist in existing dashboards, and to update rows if
they exist in dashboards. The module will not manage rows that are not defined,
allowing users to manage their own custom rows.
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy

# Import Salt libs
import salt.utils.json
from salt.exceptions import SaltInvocationError
from salt.utils.dictdiffer import DictDiffer

# Import 3rd-party
from salt.ext.six import string_types


def __virtual__():
    '''
    Only load if grafana is available.
    '''
    return 'grafana' if 'elasticsearch.exists' in __salt__ else False


def _parse_profile(profile):
    '''
    From a pillar key, or a dictionary, return index and host keys.
    '''
    if isinstance(profile, string_types):
        _profile = __salt__['config.option'](profile)
        if not _profile:
            msg = 'Pillar key for profile {0} not found.'.format(profile)
            raise SaltInvocationError(msg)
    else:
        _profile = profile
    hosts = _profile.get('hosts')
    index = _profile.get('index')
    return (hosts, index)


def _rows_differ(row, _row):
    '''
    Check if grafana dashboard row and _row differ
    '''
    row_copy = copy.deepcopy(row)
    _row_copy = copy.deepcopy(_row)
    # Strip id from all panels in both rows, since they are always generated.
    for panel in row_copy['panels']:
        if 'id' in panel:
            del panel['id']
    for _panel in _row_copy['panels']:
        if 'id' in _panel:
            del _panel['id']
    diff = DictDiffer(row_copy, _row_copy)
    return diff.changed() or diff.added() or diff.removed()


def dashboard_present(
        name,
        dashboard=None,
        dashboard_from_pillar=None,
        rows=None,
        rows_from_pillar=None,
        profile='grafana'):
    '''
    Ensure the grafana dashboard exists and is managed.

    name
        Name of the grafana dashboard.

    dashboard
        A dict that defines a dashboard that should be managed.

    dashboard_from_pillar
        A pillar key that contains a grafana dashboard dict. Mutually exclusive
        with dashboard.

    rows
        A list of grafana rows.

    rows_from_pillar
        A list of pillar keys that contain lists of grafana dashboard rows.
        Rows defined in the pillars will be appended to the rows defined in the
        state.

    profile
        A pillar key or dict that contains a list of hosts and an
        elasticsearch index to use.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if not profile:
        raise SaltInvocationError('profile is a required argument.')
    if dashboard and dashboard_from_pillar:
        raise SaltInvocationError('dashboard and dashboard_from_pillar are'
                                  ' mutually exclusive arguments.')
    hosts, index = _parse_profile(profile)
    if not index:
        raise SaltInvocationError('index is a required key in the profile.')

    if not dashboard:
        dashboard = __salt__['pillar.get'](dashboard_from_pillar)
    if not rows:
        rows = []
    if rows_from_pillar:
        for key in rows_from_pillar:
            pillar_rows = __salt__['pillar.get'](key)
            # Pillar contains a list of rows
            if isinstance(pillar_rows, list):
                for row in pillar_rows:
                    rows.append(row)
            # Pillar contains a single row
            else:
                rows.append(pillar_rows)

    exists = __salt__['elasticsearch.exists'](
        index=index, id=name, doc_type='dashboard', hosts=hosts
    )

    if exists:
        _dashboard = __salt__['elasticsearch.get'](
            index=index, id=name, doc_type='dashboard', hosts=hosts
        )
        _dashboard = _dashboard.get('_source', {}).get('dashboard')
        _dashboard = salt.utils.json.loads(_dashboard)
    else:
        if not dashboard:
            raise SaltInvocationError('Grafana dashboard does not exist and no'
                                      ' dashboard template was provided.')
        if __opts__['test']:
            ret['comment'] = 'Dashboard {0} is set to be created.'.format(
                name
            )
            ret['result'] = None
            return ret
        _dashboard = dashboard
    update_rows = []
    _ids = []
    _data = {}
    for _n, _row in enumerate(_dashboard['rows']):
        # Collect the unique ids
        for _panel in _row['panels']:
            if 'id' in _panel:
                _ids.append(_panel['id'])
        # Collect all of the titles in the existing dashboard
        if 'title' in _row:
            _data[_row['title']] = _n
    _ids.sort()
    if not _ids:
        _ids = [1]
    for row in rows:
        if 'title' not in row:
            raise SaltInvocationError('title is a required key for rows.')
        # Each panel needs to have a unique ID
        for panel in row['panels']:
            _ids.append(_ids[-1] + 1)
            panel['id'] = _ids[-1]
        title = row['title']
        # If the title doesn't exist, we need to add this row
        if title not in _data:
            update_rows.append(title)
            _dashboard['rows'].append(row)
            continue
        # For existing titles, replace the row if it differs
        _n = _data[title]
        if _rows_differ(row, _dashboard['rows'][_n]):
            _dashboard['rows'][_n] = row
            update_rows.append(title)
    if not update_rows:
        ret['result'] = True
        ret['comment'] = 'Dashboard {0} is up to date'.format(name)
        return ret
    if __opts__['test']:
        msg = 'Dashboard {0} is set to be updated.'.format(name)
        if update_rows:
            msg = '{0} The following rows set to be updated: {1}'.format(
                msg, update_rows
            )
        ret['comment'] = msg
        return ret
    body = {
        'user':  'guest',
        'group': 'guest',
        'title': name,
        'dashboard': salt.utils.json.dumps(_dashboard)
    }
    updated = __salt__['elasticsearch.index'](
        index=index, doc_type='dashboard', body=body, id=name,
        hosts=hosts
    )
    if updated:
        ret['result'] = True
        ret['changes']['changed'] = name
        msg = 'Updated dashboard {0}.'.format(name)
        if update_rows:
            msg = '{0} The following rows were updated: {1}'.format(
                msg, update_rows
            )
        ret['comment'] = msg
    else:
        ret['result'] = False
        msg = 'Failed to update dashboard {0}.'.format(name)
        ret['comment'] = msg

    return ret


def dashboard_absent(
        name,
        hosts=None,
        profile='grafana'):
    '''
    Ensure the named grafana dashboard is deleted.

    name
        Name of the grafana dashboard.

    profile
        A pillar key or dict that contains a list of hosts and an
        elasticsearch index to use.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    hosts, index = _parse_profile(profile)
    if not index:
        raise SaltInvocationError('index is a required key in the profile.')

    exists = __salt__['elasticsearch.exists'](
        index=index, id=name, doc_type='dashboard', hosts=hosts
    )

    if exists:
        if __opts__['test']:
            ret['comment'] = 'Dashboard {0} is set to be removed.'.format(
                name
            )
            return ret
        deleted = __salt__['elasticsearch.delete'](
            index=index, doc_type='dashboard', id=name, hosts=hosts
        )
        if deleted:
            ret['result'] = True
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} dashboard.'.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'Dashboard {0} does not exist.'.format(name)

    return ret

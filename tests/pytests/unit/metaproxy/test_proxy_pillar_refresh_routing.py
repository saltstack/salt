"""
Unit tests pinning how a ``pillar_refresh`` event is routed to the object
whose ``pillar_refresh`` re-packs the proxy loader (issue #58197).

The #58197 fix lives in ``Minion.pillar_refresh``. For a standard proxy that
is the proxy minion itself. For deltaproxy, ``Minion.handle_event`` dispatches
each sub-proxy's ``pillar_refresh`` event to *that sub-proxy* instance
(``_minion = self.deltaproxy_objs[proxy_target]``), so the same single re-pack
runs per sub-proxy against the sub-proxy's own loader and opts. These tests
lock that routing down so the deltaproxy coverage cannot silently regress.
"""

import tornado.concurrent

import salt.minion
import salt.utils.event
from tests.support.mock import MagicMock, patch


def _resolved_future(*args, **kwargs):
    future = tornado.concurrent.Future()
    future.set_result(None)
    return future


async def _drive_handle_event(minion, tag, data):
    with patch.object(salt.utils.event.SaltEvent, "unpack", return_value=(tag, data)):
        await minion.handle_event(b"package")


async def test_pillar_refresh_event_routes_to_subproxy():
    """
    A ``pillar_refresh`` event carrying ``proxy_target`` must be handled by the
    matching sub-proxy's ``pillar_refresh`` (where the loader re-pack happens),
    not the control proxy's.
    """
    minion = salt.minion.ProxyMinion.__new__(salt.minion.ProxyMinion)
    minion.ready = True
    minion.opts = {"metaproxy": "deltaproxy", "master": "master"}
    minion.pillar_refresh = MagicMock(side_effect=_resolved_future)

    sub_a = MagicMock()
    sub_a.pillar_refresh.side_effect = _resolved_future
    sub_b = MagicMock()
    sub_b.pillar_refresh.side_effect = _resolved_future
    minion.deltaproxy_objs = {"sub-a": sub_a, "sub-b": sub_b}

    await _drive_handle_event(
        minion,
        "pillar_refresh",
        {"proxy_target": "sub-a", "clean_cache": False, "force_refresh": False},
    )

    sub_a.pillar_refresh.assert_called_once()
    sub_b.pillar_refresh.assert_not_called()
    minion.pillar_refresh.assert_not_called()


async def test_pillar_refresh_event_without_proxy_target_routes_to_self():
    """
    Without ``proxy_target`` (standard proxy / control proxy) the event is
    handled by the minion itself, so its own ``pillar_refresh`` re-packs its
    own loader.
    """
    minion = salt.minion.ProxyMinion.__new__(salt.minion.ProxyMinion)
    minion.ready = True
    minion.opts = {"metaproxy": "deltaproxy", "master": "master"}
    minion.pillar_refresh = MagicMock(side_effect=_resolved_future)
    minion.deltaproxy_objs = {"sub-a": MagicMock()}

    await _drive_handle_event(
        minion,
        "pillar_refresh",
        {"clean_cache": False, "force_refresh": False},
    )

    minion.pillar_refresh.assert_called_once()
    minion.deltaproxy_objs["sub-a"].pillar_refresh.assert_not_called()

"""WebSocket publications must reach shared DeltaProxy connections."""

import pytest

import salt.payload
import salt.transport.ws
from tests.support.mock import AsyncMock, MagicMock

pytestmark = [pytest.mark.core_test]


@pytest.mark.parametrize(
    "topics", [None, [], ["child-one"], ["child-one", "child-two"], ["controller"]]
)
async def test_publish_reaches_shared_controller(master_opts, topics):
    server = salt.transport.ws.PublishServer(master_opts)
    controller = MagicMock()
    controller.send_bytes = AsyncMock()
    server.clients = {controller}
    try:
        await server.publish_payload(b"encrypted-job", topic_list=topics)
        expected = salt.payload.dumps(b"encrypted-job", use_bin_type=True)
        controller.send_bytes.assert_awaited_once_with(expected)
    finally:
        server.close()

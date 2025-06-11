import pytest

import salt.returners.sqlalchemy as returner
from tests.support.mock import patch

sqlalchemy = pytest.importorskip("sqlalchemy")


@pytest.fixture
def configure_loader_modules():
    return {returner: {"__opts__": {}, "__context__": {}}}


def test_retry_exhaustion_raises_and_logs(caplog):
    attempts = []

    @returner.retry_on_failure
    def store():
        attempts.append(True)
        raise sqlalchemy.exc.OperationalError("INSERT", {}, RuntimeError("offline"))

    with patch.dict(
        returner.__opts__,
        {"returner.sqlalchemy.max_retries": 2, "returner.sqlalchemy.retry_delay": 0},
    ), patch("salt.returners.sqlalchemy.time.sleep") as sleep:
        with pytest.raises(sqlalchemy.exc.OperationalError):
            store()
    assert len(attempts) == 2
    sleep.assert_called_once_with(0)
    assert "store failed after 2 attempts" in caplog.text

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src import app as app_module


@pytest.fixture
def isolated_activities(monkeypatch):
    activities = deepcopy(app_module.activities)
    monkeypatch.setattr(app_module, "activities", activities)
    return activities


@pytest.fixture
def client(isolated_activities, monkeypatch):
    monkeypatch.setenv("ACTIVITY_ADMIN_TOKEN", "test-admin-token")
    with TestClient(app_module.app) as test_client:
        yield test_client
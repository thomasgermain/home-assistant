"""Fixtures for multimatic tests."""

from unittest import mock

import pytest

from tests.components.multimatic import SystemManagerMock


@pytest.fixture(name="mock_system_manager")
def fixture_mock_system_manager():
    """Mock the multimatic system manager."""
    with mock.patch("pymultimatic.systemmanager.SystemManager", new=SystemManagerMock):
        yield
    SystemManagerMock.reset_mock()

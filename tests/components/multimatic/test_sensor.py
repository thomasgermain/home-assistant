"""Tests for the multimatic sensor."""

from pymultimatic.model import System
import pytest

import homeassistant.components.multimatic as multimatic

from tests.components.multimatic import (
    SystemManagerMock,
    assert_entities_count,
    goto_future,
    setup_multimatic,
)


@pytest.fixture(autouse=True)
def fixture_only_sensor(mock_system_manager):
    """Mock multimatic to only handle sensor."""
    orig_platforms = multimatic.PLATFORMS
    multimatic.PLATFORMS = ["sensor"]
    yield
    multimatic.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_multimatic(hass)
    assert_entities_count(hass, 2)


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await setup_multimatic(hass, system=System())
    assert_entities_count(hass, 0)


async def test_state_update(hass):
    """Test all sensors are updated accordingly to data."""
    assert await setup_multimatic(hass)
    assert_entities_count(hass, 2)

    assert hass.states.is_state("sensor.waterpressuresensor", "1.9")
    assert hass.states.is_state("sensor.outdoor_temperature", "18")

    system = SystemManagerMock.system
    system.outdoor_temperature = 21
    system.reports[0].value = 1.6
    SystemManagerMock.system = system

    await goto_future(hass)

    assert hass.states.is_state("sensor.waterpressuresensor", "1.6")
    assert hass.states.is_state("sensor.outdoor_temperature", "21")

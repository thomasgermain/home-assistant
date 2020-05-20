"""Tests for the multimatic fan."""
from pymultimatic.model import QuickModes
import pytest

import homeassistant.components.multimatic as multimatic

from tests.components.multimatic import (
    SystemManagerMock,
    assert_entities_count,
    call_service,
    get_system,
    setup_multimatic,
    ventilation,
)


@pytest.fixture(autouse=True)
def fixture_only_fan(mock_system_manager):
    """Mock multimatic to only handle fan."""
    orig_platforms = multimatic.PLATFORMS
    multimatic.PLATFORMS = ["fan"]
    yield
    multimatic.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    system = get_system()
    system.ventilation = ventilation()
    assert await setup_multimatic(hass, system=system)
    assert_entities_count(hass, 1)
    assert hass.states.is_state("fan.ventilation", "on")


async def test_turn_on(hass):
    """Test turn on."""
    system = get_system()
    system.ventilation = ventilation()
    assert await setup_multimatic(hass, system=system)

    await call_service(hass, "fan", "turn_on", {"entity_id": "fan.ventilation"})

    SystemManagerMock.instance.set_ventilation_operating_mode.assert_called_once()
    assert hass.states.is_state("fan.ventilation", "on")


async def test_turn_off(hass):
    """Test turn off."""
    system = get_system()
    system.ventilation = ventilation()
    assert await setup_multimatic(hass, system=system)

    await call_service(hass, "fan", "turn_off", {"entity_id": "fan.ventilation"})

    SystemManagerMock.instance.set_ventilation_operating_mode.assert_called_once()
    assert hass.states.is_state("fan.ventilation", "off")


async def test_set_speed(hass):
    """Test set speed."""
    system = get_system()
    system.ventilation = ventilation()
    assert await setup_multimatic(hass, system=system)

    await call_service(
        hass, "fan", "set_speed", {"entity_id": "fan.ventilation", "speed": "AUTO"}
    )

    SystemManagerMock.instance.set_ventilation_operating_mode.assert_called_once()
    assert hass.states.is_state("fan.ventilation", "on")


async def test_boost_quick_mode(hass):
    """Test with quick boost."""
    system = get_system()
    system.ventilation = ventilation()
    system.quick_mode = QuickModes.VENTILATION_BOOST
    assert await setup_multimatic(hass, system=system)

    assert hass.states.is_state("fan.ventilation", "on")

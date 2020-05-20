"""Tests for the multimatic zone climate."""

import logging

from pymultimatic.model import (
    ActiveFunction,
    OperatingModes,
    QuickMode,
    QuickModes,
    QuickVeto,
    SettingModes,
    System,
    Zone,
)
import pytest

from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
)
import homeassistant.components.multimatic as multimatic
from homeassistant.components.multimatic.const import (
    ATTR_ENDS_AT,
    ATTR_MULTIMATIC_MODE,
    PRESET_DAY,
    PRESET_HOLIDAY,
    PRESET_PARTY,
    PRESET_QUICK_VETO,
    PRESET_SYSTEM_OFF,
)

from tests.components.multimatic import (
    SystemManagerMock,
    active_holiday_mode,
    assert_entities_count,
    call_service,
    get_system,
    goto_future,
    setup_multimatic,
    time_program,
)

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def fixture_only_climate(mock_system_manager):
    """Mock multimatic to only handle sensor."""
    orig_platforms = multimatic.PLATFORMS
    multimatic.PLATFORMS = ["climate"]
    yield
    multimatic.PLATFORMS = orig_platforms


def _assert_zone_state(hass, mode, hvac, current_temp, target_temp, preset, action):
    """Assert zone climate state."""
    state = hass.states.get("climate.zone_1")

    assert hass.states.is_state("climate.zone_1", hvac)
    assert state.attributes["current_temperature"] == current_temp
    assert state.attributes["max_temp"] == Zone.MAX_TARGET_TEMP
    assert state.attributes["min_temp"] == Zone.MIN_TARGET_HEATING_TEMP
    assert state.attributes["temperature"] == target_temp
    assert state.attributes["hvac_action"] == action
    assert state.attributes["preset_mode"] == preset

    expected_modes = {
        HVAC_MODE_OFF,
        HVAC_MODE_AUTO,
    }

    zone = SystemManagerMock.system.zones[0]
    if zone.cooling:
        expected_modes.update({HVAC_MODE_COOL})

    assert set(state.attributes["hvac_modes"]) == expected_modes
    assert state.attributes[ATTR_MULTIMATIC_MODE] == mode.name


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_multimatic(hass)
    # one room, one zone
    assert_entities_count(hass, 2)
    zone = SystemManagerMock.system.zones[0]
    _assert_zone_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        zone.temperature,
        zone.active_mode.target,
        PRESET_COMFORT,
        CURRENT_HVAC_HEAT,
    )


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await setup_multimatic(hass, system=System())
    assert_entities_count(hass, 0)


async def _test_mode_hvac(
    hass, mode, function, hvac_mode, target_temp, preset, action, system=None
):
    system = get_system() if system is None else system

    if isinstance(mode, QuickMode):
        system.quick_mode = mode
    else:
        system.zones[0].heating.operating_mode = mode

    system.zones[0].active_function = function

    assert await setup_multimatic(hass, system=system)
    zone = SystemManagerMock.system.zones[0]
    _assert_zone_state(
        hass, mode, hvac_mode, zone.temperature, target_temp, preset, action
    )


async def _test_set_hvac(
    hass,
    mode,
    function,
    hvac_mode,
    current_temp,
    target_temp,
    preset,
    action,
    system=None,
):
    system = get_system() if system is None else system
    system.zones[0].active_function = function
    assert await setup_multimatic(hass, system=system)

    await call_service(
        hass,
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.zone_1", "hvac_mode": hvac_mode},
    )

    _assert_zone_state(hass, mode, hvac_mode, current_temp, target_temp, preset, action)


async def test_day_mode_hvac_heat(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass,
        OperatingModes.DAY,
        ActiveFunction.HEATING,
        HVAC_MODE_HEAT,
        zone.heating.target_high,
        PRESET_DAY,
        CURRENT_HVAC_HEAT,
    )


async def test_day_mode_hvac_idle(hass):
    """Test mode <> hvac."""
    system = get_system()
    zone = system.zones[0]
    zone.temperature = 20
    zone.heating.target_high = 15
    zone.heating.target_low = 10
    await _test_mode_hvac(
        hass,
        OperatingModes.DAY,
        ActiveFunction.STANDBY,
        "unknown",
        zone.heating.target_high,
        PRESET_DAY,
        CURRENT_HVAC_IDLE,
        system,
    )


async def test_night_mode_hvac_idle(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass,
        OperatingModes.NIGHT,
        ActiveFunction.STANDBY,
        "unknown",
        zone.heating.target_low,
        PRESET_SLEEP,
        CURRENT_HVAC_IDLE,
    )


async def test_auto_mode_hvac_auto(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass,
        OperatingModes.AUTO,
        ActiveFunction.STANDBY,
        HVAC_MODE_AUTO,
        zone.active_mode.target,
        PRESET_COMFORT,
        CURRENT_HVAC_IDLE,
    )


async def test_off_mode_hvac_off(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    zone.heating.operating_mode = OperatingModes.OFF
    await _test_mode_hvac(
        hass,
        OperatingModes.OFF,
        ActiveFunction.STANDBY,
        HVAC_MODE_OFF,
        Zone.MIN_TARGET_HEATING_TEMP,
        PRESET_NONE,
        CURRENT_HVAC_IDLE,
    )


async def test_quickmode_system_off_mode_hvac_off(hass):
    """Test mode <> hvac."""
    await _test_mode_hvac(
        hass,
        QuickModes.SYSTEM_OFF,
        ActiveFunction.STANDBY,
        HVAC_MODE_OFF,
        Zone.MIN_TARGET_HEATING_TEMP,
        PRESET_SYSTEM_OFF,
        CURRENT_HVAC_IDLE,
    )


async def test_quickmode_one_day_away_mode_hvac_off(hass):
    """Test mode <> hvac."""
    await _test_mode_hvac(
        hass,
        QuickModes.ONE_DAY_AWAY,
        ActiveFunction.STANDBY,
        HVAC_MODE_OFF,
        Zone.MIN_TARGET_HEATING_TEMP,
        PRESET_AWAY,
        CURRENT_HVAC_IDLE,
    )


async def test_quickmode_party_mode_hvac(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass,
        QuickModes.PARTY,
        ActiveFunction.STANDBY,
        "unknown",
        zone.heating.target_high,
        PRESET_PARTY,
        CURRENT_HVAC_IDLE,
    )


async def test_quickmode_one_day_home_hvac_auto(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass,
        QuickModes.ONE_DAY_AT_HOME,
        ActiveFunction.STANDBY,
        HVAC_MODE_AUTO,
        zone.heating.target_low,
        PRESET_HOME,
        CURRENT_HVAC_IDLE,
    )


async def test_quickmode_ventilation_boost_hvac_fan(hass):
    """Test mode <> hvac."""
    await _test_mode_hvac(
        hass,
        QuickModes.VENTILATION_BOOST,
        ActiveFunction.STANDBY,
        HVAC_MODE_FAN_ONLY,
        Zone.MIN_TARGET_HEATING_TEMP,
        PRESET_NONE,
        CURRENT_HVAC_IDLE,
    )


async def test_holiday_hvac_off(hass):
    """Test mode <> hvac."""
    system = get_system()
    system.holiday = active_holiday_mode()

    await _test_mode_hvac(
        hass,
        QuickModes.HOLIDAY,
        ActiveFunction.STANDBY,
        HVAC_MODE_OFF,
        15,
        PRESET_HOLIDAY,
        CURRENT_HVAC_IDLE,
        system,
    )


async def test_set_hvac_auto(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_set_hvac(
        hass,
        OperatingModes.AUTO,
        ActiveFunction.STANDBY,
        HVAC_MODE_AUTO,
        zone.temperature,
        zone.active_mode.target,
        PRESET_COMFORT,
        CURRENT_HVAC_IDLE,
    )


async def test_set_hvac_off(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_set_hvac(
        hass,
        OperatingModes.OFF,
        ActiveFunction.STANDBY,
        HVAC_MODE_OFF,
        zone.temperature,
        Zone.MIN_TARGET_HEATING_TEMP,
        PRESET_NONE,
        CURRENT_HVAC_IDLE,
    )


async def test_set_target_temp_cool(hass):
    """Test mode <> hvac."""
    system = get_system()
    system.zones[0].active_function = ActiveFunction.STANDBY
    assert await setup_multimatic(hass, system=system)

    await call_service(
        hass,
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_1", "temperature": 14},
    )

    _assert_zone_state(
        hass,
        OperatingModes.QUICK_VETO,
        "unknown",
        system.zones[0].temperature,
        14,
        PRESET_QUICK_VETO,
        CURRENT_HVAC_IDLE,
    )
    SystemManagerMock.instance.set_zone_quick_veto.assert_called_once()


async def test_set_target_temp_heat(hass):
    """Test mode <> hvac."""
    system = get_system()
    system.zones[0].active_function = ActiveFunction.HEATING
    assert await setup_multimatic(hass, system=system)

    await call_service(
        hass,
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_1", "temperature": 30},
    )

    _assert_zone_state(
        hass,
        OperatingModes.QUICK_VETO,
        HVAC_MODE_HEAT,
        system.zones[0].temperature,
        30,
        PRESET_QUICK_VETO,
        CURRENT_HVAC_HEAT,
    )
    SystemManagerMock.instance.set_zone_quick_veto.assert_called_once()


async def test_state_update_zone(hass):
    """Test zone climate is updated accordingly to data."""
    assert await setup_multimatic(hass)
    zone = SystemManagerMock.system.zones[0]
    _assert_zone_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        zone.temperature,
        zone.active_mode.target,
        PRESET_COMFORT,
        CURRENT_HVAC_HEAT,
    )

    system = SystemManagerMock.system
    zone = system.zones[0]
    zone.heating.target_high = 30
    zone.heating.time_program = time_program(SettingModes.DAY, None)
    zone.temperature = 25
    zone.active_function = ActiveFunction.HEATING
    await goto_future(hass)

    _assert_zone_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        25,
        30,
        PRESET_COMFORT,
        CURRENT_HVAC_HEAT,
    )


async def test_state_attrs_quick_veto(hass):
    """Test state_attrs are correct."""
    system = get_system()
    system.zones[0].quick_veto = QuickVeto(duration=None, target=15)
    assert await setup_multimatic(hass, system=system)
    state = hass.states.get("climate.zone_1")
    assert state.attributes.get(ATTR_ENDS_AT, None) is None

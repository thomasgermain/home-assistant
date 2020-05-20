"""Tests for the multimatic sensor."""

from pymultimatic.model import (
    ActiveFunction,
    OperatingModes,
    QuickMode,
    QuickModes,
    QuickVeto,
    Room,
    System,
)
import pytest

from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_COMFORT,
    PRESET_NONE,
)
import homeassistant.components.multimatic as multimatic
from homeassistant.components.multimatic.const import (
    ATTR_ENDS_AT,
    ATTR_MULTIMATIC_MODE,
    PRESET_HOLIDAY,
    PRESET_MANUAL,
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


def _assert_room_state(hass, mode, hvac, current_temp, temp, preset, action):
    """Assert room climate state."""
    state = hass.states.get("climate.room_1")

    assert hass.states.is_state("climate.room_1", hvac)
    assert state.attributes["current_temperature"] == current_temp
    assert state.attributes["max_temp"] == Room.MAX_TARGET_TEMP
    assert state.attributes["min_temp"] == Room.MIN_TARGET_TEMP
    assert state.attributes["temperature"] == temp
    assert state.attributes[ATTR_MULTIMATIC_MODE] == mode.name
    assert state.attributes["hvac_action"] == action
    assert state.attributes["preset_mode"] == preset


@pytest.fixture(autouse=True)
def fixture_only_climate(mock_system_manager):
    """Mock multimatic to only handle sensor."""
    orig_platforms = multimatic.PLATFORMS
    multimatic.PLATFORMS = ["climate"]
    yield
    multimatic.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_multimatic(hass)
    assert_entities_count(hass, 2)
    _assert_room_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        22,
        20,
        PRESET_COMFORT,
        CURRENT_HVAC_IDLE,
    )


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await setup_multimatic(hass, system=System())
    assert_entities_count(hass, 0)


async def test_state_update_room(hass):
    """Test room climate is updated accordingly to data."""
    assert await setup_multimatic(hass)
    _assert_room_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        22,
        20,
        PRESET_COMFORT,
        CURRENT_HVAC_IDLE,
    )

    system = SystemManagerMock.system
    room = system.rooms[0]
    room.temperature = 25
    room.target_high = 30
    room.time_program = time_program(None, 30)
    rbr_zone = [zone for zone in system.zones if zone.rbr][0]
    rbr_zone.active_function = ActiveFunction.HEATING
    await goto_future(hass)

    _assert_room_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        25,
        30,
        PRESET_COMFORT,
        CURRENT_HVAC_HEAT,
    )


async def _test_mode_hvac(hass, mode, function, hvac_mode, target_temp, preset, action):
    system = get_system()

    if isinstance(mode, QuickMode):
        system.quick_mode = mode
    else:
        system.rooms[0].operating_mode = mode

    rbr_zone = [zone for zone in system.zones if zone.rbr][0]
    rbr_zone.active_function = function

    assert await setup_multimatic(hass, system=system)
    room = SystemManagerMock.system.rooms[0]
    _assert_room_state(
        hass, mode, hvac_mode, room.temperature, target_temp, preset, action
    )


async def test_auto_mode_hvac_auto(hass):
    """Test with auto mode."""
    room = get_system().rooms[0]
    await _test_mode_hvac(
        hass,
        OperatingModes.AUTO,
        ActiveFunction.HEATING,
        HVAC_MODE_AUTO,
        room.active_mode.target,
        PRESET_COMFORT,
        CURRENT_HVAC_IDLE,
    )


async def test_off_mode_hvac_off(hass):
    """Test with off mode."""
    await _test_mode_hvac(
        hass,
        OperatingModes.OFF,
        "IDLE",
        HVAC_MODE_OFF,
        Room.MIN_TARGET_TEMP,
        PRESET_NONE,
        CURRENT_HVAC_IDLE,
    )


async def test_quickmode_system_off_mode_hvac_off(hass):
    """Test with quick mode off."""
    await _test_mode_hvac(
        hass,
        QuickModes.SYSTEM_OFF,
        "IDLE",
        HVAC_MODE_OFF,
        Room.MIN_TARGET_TEMP,
        PRESET_SYSTEM_OFF,
        CURRENT_HVAC_IDLE,
    )


async def test_holiday_mode(hass):
    """Test with holiday mode."""
    system = get_system()
    system.holiday = active_holiday_mode()
    rbr_zone = [zone for zone in system.zones if zone.rbr][0]
    rbr_zone.active_function = "IDLE"

    assert await setup_multimatic(hass, system=system)

    _assert_room_state(
        hass,
        QuickModes.HOLIDAY,
        HVAC_MODE_OFF,
        system.rooms[0].temperature,
        15,
        PRESET_HOLIDAY,
        CURRENT_HVAC_IDLE,
    )


async def test_set_target_temp_cool(hass):
    """Test hvac is cool with lower target temp."""
    system = get_system()
    room = system.rooms[0]
    rbr_zone = [zone for zone in system.zones if zone.rbr][0]
    rbr_zone.active_function = "IDLE"
    assert await setup_multimatic(hass, system=system)

    await call_service(
        hass,
        "climate",
        "set_temperature",
        {"entity_id": "climate.room_1", "temperature": 14},
    )

    _assert_room_state(
        hass,
        OperatingModes.QUICK_VETO,
        "unknown",
        room.temperature,
        14,
        PRESET_QUICK_VETO,
        CURRENT_HVAC_IDLE,
    )
    SystemManagerMock.instance.set_room_quick_veto.assert_called_once()


async def test_set_target_temp_heat(hass):
    """Test hvac is heat with higher target temp."""
    system = get_system()
    room = system.rooms[0]
    rbr_zone = [zone for zone in system.zones if zone.rbr][0]
    rbr_zone.active_function = ActiveFunction.HEATING
    assert await setup_multimatic(hass, system=system)

    await call_service(
        hass,
        "climate",
        "set_temperature",
        {"entity_id": "climate.room_1", "temperature": 30},
    )

    _assert_room_state(
        hass,
        OperatingModes.QUICK_VETO,
        HVAC_MODE_HEAT,
        room.temperature,
        30,
        PRESET_QUICK_VETO,
        CURRENT_HVAC_HEAT,
    )
    SystemManagerMock.instance.set_room_quick_veto.assert_called_once()


async def test_room_manual(hass):
    """Test hvac is heating with higher target temp."""
    system = get_system()
    room = system.rooms[0]
    room.operating_mode = OperatingModes.MANUAL
    room.temperature = 15
    room.target_high = 25
    rbr_zone = [zone for zone in system.zones if zone.rbr][0]
    rbr_zone.active_function = ActiveFunction.HEATING

    assert await setup_multimatic(hass, system=system)
    _assert_room_state(
        hass,
        OperatingModes.MANUAL,
        HVAC_MODE_HEAT,
        15,
        25,
        PRESET_MANUAL,
        CURRENT_HVAC_HEAT,
    )


async def test_room_manual_cool(hass):
    """Test hvac is not heating at higher target temp."""
    system = get_system()
    room = system.rooms[0]
    room.operating_mode = OperatingModes.MANUAL
    room.temperature = 20
    room.target_high = 18
    rbr_zone = [zone for zone in system.zones if zone.rbr][0]
    rbr_zone.active_function = "IDLE"

    assert await setup_multimatic(hass, system=system)
    _assert_room_state(
        hass, OperatingModes.MANUAL, "unknown", 20, 18, PRESET_MANUAL, CURRENT_HVAC_IDLE
    )


async def test_state_attrs_quick_veto(hass):
    """Tetst state_attrs are correct."""
    system = get_system()
    system.rooms[0].quick_veto = QuickVeto(duration=30, target=15)
    assert await setup_multimatic(hass, system=system)
    state = hass.states.get("climate.room_1")
    assert state.attributes[ATTR_ENDS_AT] is not None

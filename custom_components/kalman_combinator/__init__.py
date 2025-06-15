"""The kalman_combinator component."""
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_ENTITY_ID,
    CONF_UNIQUE_ID,
    Platform,
    CONF_ICON,
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

DOMAIN = "kalman_combinator"

CONF_SENSORS = "sensors"
CONF_STEP_DURATION = "step_duration"
CONF_STD_DEVIATION = "std_deviation"
CONF_MAX_DEVIATION = "max_deviation"
CONF_OFFSET = "offset"
CONF_OFFSET_RATE = "offset_rate"
CONF_VARIANCE_RATE = "variance_rate"
CONF_EFFECT = "effect"
CONF_CONTROLS = "controls"
CONF_SPEED_VARIANCE_RATE = "speed_variance_rate"
CONF_SPEED_STD_DEVIATION = "speed_std_deviation"
DEFAULT_STEP_DURATION = 5
DEFAULT_NAME = "Kalman Combinator"
DEFAULT_MAX_DEVIATION = (
    18  # roughly equals to uncertainty of +- 5 (FWHM of 10) in the respective units
)

KALMAN_CHILD_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_OFFSET): vol.Coerce(float),
        vol.Optional(CONF_STD_DEVIATION): vol.Coerce(float),
        vol.Optional(CONF_OFFSET_RATE): vol.Coerce(float),
        vol.Optional(CONF_VARIANCE_RATE): vol.Coerce(float),
    }
)

KALMAN_CONTROL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_EFFECT): vol.Coerce(float),
        vol.Optional(CONF_OFFSET_RATE): vol.Coerce(float),
    }
)

KALMAN_COMBINATOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_STEP_DURATION, default=DEFAULT_STEP_DURATION): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(CONF_STD_DEVIATION): vol.Coerce(float),
        vol.Optional(CONF_VARIANCE_RATE): vol.Coerce(float),
        vol.Optional(CONF_SPEED_STD_DEVIATION): vol.Coerce(float),
        vol.Optional(CONF_SPEED_VARIANCE_RATE): vol.Coerce(float),
        vol.Optional(CONF_MAX_DEVIATION, default=DEFAULT_MAX_DEVIATION): vol.Coerce(
            float
        ),
        vol.Required(CONF_SENSORS): vol.All(
            cv.ensure_list, [KALMAN_CHILD_SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_CONTROLS): vol.All(cv.ensure_list, [KALMAN_CONTROL_SCHEMA]),
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_DEVICE_CLASS): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [KALMAN_COMBINATOR_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Kalman Combinator component."""
    if DOMAIN not in config:
        return True

    for kalman_combinator_conf in config[DOMAIN]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.SENSOR, DOMAIN, kalman_combinator_conf, config
            )
        )

    return True

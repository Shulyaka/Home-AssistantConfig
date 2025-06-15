"""Adds support for kalman_combinator sensors."""
from __future__ import annotations

import logging

import numpy as np
from homeassistant.components.sensor import (  # SensorStateClass,
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_CONTROLS,
    CONF_EFFECT,
    CONF_MAX_DEVIATION,
    CONF_OFFSET,
    CONF_OFFSET_RATE,
    CONF_SENSORS,
    CONF_STD_DEVIATION,
    CONF_SPEED_VARIANCE_RATE,
    CONF_SPEED_STD_DEVIATION,
    CONF_STEP_DURATION,
    CONF_VARIANCE_RATE,
    KALMAN_COMBINATOR_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SPEED = "current_speed"
ATTR_VARIANCE = "model_step_variance"
ATTR_SPEED_VARIANCE = "model_step_speed_variance"
ATTR_P = "estimation_variance"
ATTR_P01 = "estimation_state_by_speed_cross_variance"
ATTR_P11 = "estimation_speed_variance"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(KALMAN_COMBINATOR_SCHEMA.schema)


DEFAULT_SENSOR_OFFSET_RATE = 0.001
DEFAULT_SENSOR_VARIANCE_RATE = 0.001
DEFAULT_MODEL_OFFSET_RATE = 0.001
DEFAULT_MODEL_VARIANCE_RATE = 0.001
RATELIMIT = 0.1


class SensorParams(object):
    def __init__(self, config):
        self.entity_id = config[CONF_ENTITY_ID]
        self._config_offset = config.get(CONF_OFFSET, 0.0)
        self._variance_rate = config.get(CONF_VARIANCE_RATE)
        self._variance = config.get(CONF_STD_DEVIATION)
        if self._variance:
            self._variance *= self._variance
        elif self._variance_rate is None:
            self._variance_rate = DEFAULT_SENSOR_VARIANCE_RATE
        self._offset_rate = config.get(CONF_OFFSET_RATE, DEFAULT_SENSOR_OFFSET_RATE)

        self._state = None
        self._offset = 0.0

    def update(self, hass):
        state = hass.states.get(self.entity_id)
        if state is None:
            return
        try:
            self._state = float(state.state)
        except ValueError:
            self._state = None

    @property
    def value(self):
        if self._state is None:
            return None
        return self._state + self._config_offset

    @property
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, value):
        self._offset = value

    @property
    def variance(self):
        return self._variance

    @variance.setter
    def variance(self, value):
        if self._variance is None:
            self._variance = value

    def update_calibration(self, avg):
        if self._state is None:
            return

        self._offset += self._offset_rate * (self.value - self._offset - avg)

        deviation = self.value - self._offset - avg
        var_upd = deviation * deviation
        if self._variance is None:
            if not var_upd:
                var_upd = 1.0
            self._variance = var_upd
        else:
            self._variance += self._variance_rate * (var_upd - self._variance)


class ControlParams(object):
    def __init__(self, config):
        self.entity_id = config[CONF_ENTITY_ID]
        self._effect = config.get(CONF_EFFECT)
        self._offset_rate = config.get(CONF_OFFSET_RATE)

        if self._effect is None and self._offset_rate is None:
            self._offset_rate = DEFAULT_MODEL_OFFSET_RATE
        self._state = None

    def update(self, hass):
        state = hass.states.get(self.entity_id)
        if state is None:
            return
        try:
            self._state = float(state.state)
        except ValueError:
            self._state = 0.0
        if state.state == STATE_ON:
            self._state = 1.0

    @property
    def value(self):
        if self._state is None:
            return 0.0
        return self._state

    @property
    def effect(self):
        if self._effect is None:
            return 0.0
        return self._effect

    @effect.setter
    def effect(self, value):
        if self._effect is None:
            self._effect = value

    def update_calibration(self, avg, avg_prev):
        if self._state is None:
            return
        if self._effect is None:
            self._effect = 0.0
        if self.value:
            self._effect += self._offset_rate * (avg - avg_prev) / self.value


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the kalman_combinator platform."""
    if discovery_info:
        config = discovery_info
    name = config[CONF_NAME]
    unique_id = config.get(CONF_UNIQUE_ID)
    step_duration = config[CONF_STEP_DURATION]
    variance = config.get(CONF_STD_DEVIATION)
    if variance:
        variance *= variance
    variance_rate = config.get(CONF_VARIANCE_RATE)
    speed_variance = config.get(CONF_SPEED_STD_DEVIATION)
    if speed_variance:
        speed_variance *= speed_variance
    speed_variance_rate = config.get(CONF_SPEED_VARIANCE_RATE)
    max_variance = config[CONF_MAX_DEVIATION]
    max_variance *= max_variance
    sensors = []
    for sensor_config in config[CONF_SENSORS]:
        sensors.append(SensorParams(sensor_config))
    controls = []
    for control_config in config.get(CONF_CONTROLS, []):
        controls.append(ControlParams(control_config))
    icon = config.get(CONF_ICON)
    device_class = config.get(CONF_DEVICE_CLASS)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    for sensor in sensors:
        state = hass.states.get(sensor.entity_id)
        if state is None:
            continue
        if icon is None and ATTR_ICON in state.attributes:
            icon = state.attributes.get(ATTR_ICON)
        if device_class is None and ATTR_DEVICE_CLASS in state.attributes:
            device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        if unit_of_measurement is None and ATTR_UNIT_OF_MEASUREMENT in state.attributes:
            unit_of_measurement = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    entity_description = SensorEntityDescription(
        key=(name + unique_id) if unique_id is not None else name,
        name=name,
        has_entity_name=True,
        icon=icon,
        device_class=device_class,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=unit_of_measurement,
        # state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    )

    async_add_entities(
        [
            KalmanCombinatorSensor(
                name,
                unique_id,
                step_duration,
                variance,
                variance_rate,
                speed_variance,
                speed_variance_rate,
                max_variance,
                sensors,
                controls,
                icon,
                device_class,
                unit_of_measurement,
                entity_description,
            )
        ]
    )


class KalmanCombinatorSensor(SensorEntity, RestoreEntity):
    """Representation of a Kalman Sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        name,
        unique_id,
        step_duration,
        variance,
        variance_rate,
        speed_variance,
        speed_variance_rate,
        max_variance,
        sensors,
        controls,
        icon,
        device_class,
        unit_of_measurement,
        entity_description,
    ):
        """Initialize the entity."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._step_duration = step_duration
        self._variance = variance
        self._variance_rate = variance_rate
        self._speed_variance = speed_variance
        self._speed_variance_rate = speed_variance_rate
        self._max_variance = max_variance
        self._sensors = sensors
        self._controls = controls
        self._icon = icon
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self.entity_description = entity_description




        super().__init__()





        if self._variance is None and self._variance_rate is None:
            self._variance_rate = DEFAULT_MODEL_VARIANCE_RATE
        if self._speed_variance is None and self._speed_variance_rate is None:
            self._speed_variance_rate = self._variance_rate
        self._avg_prev = None
        self._speed_prev = None
        self._speed = 0.0
        self._P = np.array([[1.0, 0.0], [0.0, 1.0]])
        self._prev_saved_state = None
        self._iterations_since_save = None

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        for sensor in self._sensors:
            state = self.hass.states.get(sensor.entity_id)
            if state is None:
                continue
            if icon is None and ATTR_ICON in state.attributes:
                icon = state.attributes.get(ATTR_ICON)
            if device_class is None and ATTR_DEVICE_CLASS in state.attributes:
                device_class = state.attributes.get(ATTR_DEVICE_CLASS)
            if unit_of_measurement is None and ATTR_UNIT_OF_MEASUREMENT in state.attributes:
                unit_of_measurement = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        self.entity_description = SensorEntityDescription(
            key=(name + unique_id) if unique_id is not None else name,
            name=name,
            has_entity_name=True,
            icon=icon,
            device_class=device_class,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=unit_of_measurement,
            # state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
        )
        await super().async_added_to_hass()

        # Add listener
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_iterate, self._step_duration
            )
        )

        if (old_state := await self.async_get_last_state()) is not None:
            if not self._variance:
                try:
                    self._variance = float(old_state.attributes.get(ATTR_VARIANCE))
                except ValueError:
                    pass

            if not self._speed_variance:
                try:
                    self._speed_variance = float(
                        old_state.attributes.get(ATTR_SPEED_VARIANCE)
                    )
                except ValueError:
                    pass

            try:
                p00 = float(old_state.attributes.get(ATTR_P, 1.0))
                p01 = float(old_state.attributes.get(ATTR_P01, 0.0))
                p11 = float(old_state.attributes.get(ATTR_P11, 1.0))
                self._P = np.array([[p00, p01], [p01, p11]])
            except ValueError:
                pass

            try:
                self._attr_native_value = float(old_state.state)
            except ValueError:
                pass

            try:
                self._speed = float(old_state.attributes.get(ATTR_SPEED, 0.0))
            except ValueError:
                pass

            for sensor in self._sensors:
                try:
                    sensor.offset = float(
                        old_state.attributes.get(sensor.entity_id + "_offset")
                    )
                except ValueError:
                    pass

                try:
                    sensor.variance = float(
                        old_state.attributes.get(sensor.entity_id + "_variance")
                    )
                except ValueError:
                    pass

            for control in self._controls:
                try:
                    control.effect = float(
                        old_state.attributes.get(control.entity_id + "_effect")
                    )
                except ValueError:
                    pass

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            self._attr_native_value is not None and self._P[0, 0] <= self._max_variance
        )

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        attr = {
            ATTR_SPEED: self._speed,
            ATTR_P: self._P[0, 0],
            ATTR_P01: (self._P[0, 1] + self._P[1, 0]) / 2.0,
            ATTR_P11: self._P[1, 1],
        }
        if self._variance:
            attr[ATTR_VARIANCE] = self._variance
        if self._speed_variance:
            attr[ATTR_SPEED_VARIANCE] = self._speed_variance
        for sensor in self._sensors:
            if sensor.offset:
                attr[sensor.entity_id + "_offset"] = sensor.offset
            if sensor.variance:
                attr[sensor.entity_id + "_variance"] = sensor.variance
        for control in self._controls:
            if control.effect:
                attr[control.entity_id + "_effect"] = control.effect
        if len(attr):
            return attr
        return None

    async def _async_iterate(self, time):
        """Run one iteration of a Kalman filter."""
        for sensor in self._sensors:
            sensor.update(self.hass)
        for control in self._controls:
            control.update(self.hass)

        sensors = [sensor for sensor in self._sensors if sensor.value is not None]

        if len(sensors):
            # Sensor calibration:
            # The Kalman filter needs sensor errors to have expected value of zero. Thus we need to calibrate the measurement first.
            # Note that we cannot use the output of the Kalman filter itself for the calibration to avoid a positive feedback loop and hallucination.
            # So we use a simpler lowpass filter for that task. Given enough time, it will converge to a meaningful value.
            # Similarly, we calibrate the variance by looking at the deviance of the measurements from the mean.
            avg_new = 0
            for sensor in sensors:
                avg_new += sensor.value
            avg_new /= len(sensors)

            if len(sensors) == 1 and self._avg_prev is not None:
                sensors[0].update_calibration(self._avg_prev)
            else:
                for sensor in sensors:
                    sensor.update_calibration(avg_new)

            if self._avg_prev is not None:
                speed_new = avg_new - self._avg_prev

                if self._variance_rate:
                    deviation = speed_new
                    self._variance += self._variance_rate * (
                        deviation * deviation - self._variance
                    )

                for control in self._controls:
                    self._avg_prev += control.effect * control.value
                for control in self._controls:
                    control.update_calibration(avg_new, self._avg_prev)

                if self._speed_prev is not None:
                    if self._speed_variance_rate:
                        deviation = speed_new - self._speed_prev
                        self._speed_variance += self._speed_variance_rate * (
                            deviation * deviation - self._speed_variance
                        )

                self._speed_prev = speed_new

            self._avg_prev = avg_new

            z = np.array([sensor.value - sensor.offset for sensor in sensors])

            if self._attr_native_value is None:
                self._attr_native_value = np.mean(z)
        elif self._attr_native_value is None:
            return
        if not self._variance:
            self._variance = 1.0
        if not self._speed_variance:
            self._speed_variance = 1.0

        # Extrapolation:
        for control in self._controls:
            self._attr_native_value += control.effect * control.value
        self._attr_native_value += self._speed
        self._P += np.array(
            [
                [
                    self._P[0, 1] + self._P[1, 0] + self._P[1, 1] + self._variance,
                    self._P[1, 1],
                ],
                [self._P[1, 1], self._speed_variance],
            ]
        )

        # Correction:
        if len(sensors):
            y = z - np.array([self._attr_native_value] * len(sensors))
            S = np.array(
                [
                    [
                        self._P[0, 0] + sensors[i].variance if i == j else self._P[0, 0]
                        for i in range(len(sensors))
                    ]
                    for j in range(len(sensors))
                ]
            )
            K = np.array(
                [[self._P[0, 0]] * len(sensors), [self._P[1, 0]] * len(sensors)]
            ) @ np.linalg.inv(S)
            x_adj = K @ y
            self._attr_native_value += x_adj[0]
            self._speed += x_adj[1]
            self._P = (
                np.identity(2) - np.array([[np.sum(K[0]), 0.0], [np.sum(K[1]), 0.0]])
            ) @ self._P

        _LOGGER.debug("y: %s", y)
        _LOGGER.debug("K: %s", K)
        _LOGGER.debug("P: %s", self._P)
        # Only update if the change is significant, or if we waited long enough
        if (
            self._prev_saved_state is None
            or self._iterations_since_save is None
            or abs(self._attr_native_value - self._prev_saved_state)
            * self._iterations_since_save
            > RATELIMIT
        ):
            self._prev_saved_state = self._attr_native_value
            self._iterations_since_save = 0
            self.async_write_ha_state()
        else:
            self._iterations_since_save += 1

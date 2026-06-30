from enum import Enum

from device_state import DeviceStateChecks
from interfaces import Location, SendEvent


class SinPredkuEvents(str, Enum):
    """Event ids used by the Sin Predku location."""

    SOUND1 = "sin_predku_sound1"
    LIGHTS_OFF = "turn_off_lights"
    CLOUD_OFF = "turn_off_rele"
    END = "sin_predku_end"


class SinPredku(Location):
    """Finalni stanoviste Sin Predku."""

    name = "Sin Predku"
    config_id = "sin_predku"

    def enter_location(self, send_event: SendEvent):
        """Start the final scene."""
        self.phase = "sound1"
        self.state_checked = False
        send_event(SinPredkuEvents.SOUND1)
        send_event(SinPredkuEvents.LIGHTS_OFF)
        send_event(SinPredkuEvents.CLOUD_OFF)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == SinPredkuEvents.CLOUD_OFF:
            from locations import Finished

            self.state_checked = DeviceStateChecks.check()
            send_event(SinPredkuEvents.END)
            kontrola = self._check_initial_state(send_event)
            if not kontrola:
                send_event(SinPredku.KONTROLA_FAIL)
            return self.change_location(Finished(), send_event)

        return self

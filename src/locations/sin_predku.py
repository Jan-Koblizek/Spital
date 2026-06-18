from enum import Enum

from device_state import DeviceStateChecks
from interfaces import Location, SendEvent


class SinPredkuEvents(str, Enum):
    """Event ids used by the Sin Predku location."""

    SOUND1 = "sin_predku_sound1"
    SOUND1_OFF = "sin_predku_sound1_off"
    MUSIC = "sin_predku_music"
    MUSIC_OFF = "sin_predku_music_off"
    KONTROLA = "kontrola"
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

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == SinPredkuEvents.SOUND1_OFF and self.phase == "sound1":
            self.phase = "music"
            send_event(SinPredkuEvents.MUSIC)

        if event_id == SinPredkuEvents.MUSIC_OFF and self.phase == "music":
            from locations import Finished

            self.state_checked = DeviceStateChecks.check(lambda: send_event(SinPredkuEvents.KONTROLA))
            send_event(SinPredkuEvents.END)
            return self.change_location(Finished(), send_event)

        return self

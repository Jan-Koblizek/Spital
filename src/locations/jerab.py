from enum import Enum

from interfaces import Location, SendEvent


class JerabEvents(str, Enum):
    """Event ids used by the Jerab location."""

    SOUND1 = "jerab_sound1"
    SOUND1_OFF = "jerab_sound1_off"
    MUSIC_LOOP = "jerab_music_loop"
    MUSIC_LOOP_OFF = "jerab_music_loop_off"
    TLACITKO1 = "jerab_tlacitko1"
    SOUND4 = "jerab_sound4"
    SOUND4_OFF = "jerab_sound4_off"
    NEXT = "jerab_next"


class Jerab(Location):
    """Stanoviste Jerab."""

    name = "Jerab"
    config_id = "jerab"

    def enter_location(self, send_event: SendEvent):
        """Start the Jerab scene."""
        self.buttons_enabled = False
        self.sound4_started = False
        self.phase = "sound1"
        send_event(JerabEvents.SOUND1)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == JerabEvents.SOUND1_OFF and self.phase == "sound1":
            self.phase = "music_loop"
            self.buttons_enabled = True
            send_event(JerabEvents.MUSIC_LOOP)

        if event_id == JerabEvents.MUSIC_LOOP_OFF and self.phase == "music_loop":
            send_event(JerabEvents.MUSIC_LOOP)

        if event_id == JerabEvents.TLACITKO1 and self.buttons_enabled:
            self._start_sound4(send_event)

        if event_id == JerabEvents.SOUND4_OFF and self.phase == "sound4":
            from locations import ZivotPoddanych

            send_event(JerabEvents.NEXT)
            return self.change_location(ZivotPoddanych(), send_event)

        return self

    def _start_sound4(self, send_event: SendEvent) -> None:
        """Start sound4 once after the Jerab button is pressed."""
        if self.sound4_started:
            return

        self.sound4_started = True
        self.buttons_enabled = False
        self.phase = "sound4"
        send_event(JerabEvents.SOUND4)

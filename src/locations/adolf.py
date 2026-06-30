from enum import Enum

from interfaces import Location, SendEvent


class AdolfEvents(str, Enum):
    """Event ids used by the Adolf location."""

    SOUND1 = "adolf_sound1"
    SOUND1_OFF = "adolf_sound1_off"
    VIDEO1 = "adolf_video1"
    VIDEO1_OFF = "adolf_video1_off"
    SOUND3 = "adolf_sound3"
    SOUND3_OFF = "adolf_sound3_off"
    MUSIC_LOOP = "adolf_music_loop"
    MUSIC_LOOP_OFF = "adolf_music_loop_off"
    TLACITKO1_open = "adolf_tlacitko1-1"
    TLACITKO1_close = "adolf_tlacitko1-0"
    SOUND4 = "adolf_sound4"
    SOUND4_OFF = "adolf_sound4_off"
    NEXT = "adolf_next"


class Adolf(Location):
    """Stanoviste Adolf."""

    name = "Adolf"
    config_id = "adolf"

    def enter_location(self, send_event: SendEvent):
        """Start the Adolf sequence with sound1."""
        self.buttons_enabled = False
        self.sound4_started = False
        self.suple_otevreno = False
        self.phase = "sound1"
        send_event(AdolfEvents.SOUND1)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == AdolfEvents.SOUND1_OFF and self.phase == "sound1":
            self.phase = "video1"
            send_event(AdolfEvents.VIDEO1)
        elif event_id == AdolfEvents.VIDEO1_OFF and self.phase == "video1":
            self.phase = "sound3"
            send_event(AdolfEvents.SOUND3)
            self.buttons_enabled = True
        elif event_id == AdolfEvents.SOUND3_OFF and self.phase == "sound3":
            self.phase = "music_loop"
            send_event(AdolfEvents.MUSIC_LOOP)
        elif event_id == AdolfEvents.MUSIC_LOOP_OFF and self.phase == "music_loop":
            send_event(AdolfEvents.MUSIC_LOOP)
        elif event_id == AdolfEvents.TLACITKO1_open and self.buttons_enabled:
            print("suple otevreno")
            self.suple_otevreno = True
            self._start_sound4(send_event)
        elif event_id == AdolfEvents.TLACITKO1_close and self.suple_otevreno:
            self.buttons_enabled = False
        elif event_id == AdolfEvents.SOUND4_OFF and self.phase == "sound4":
            from locations import ObchodStoleti

            send_event(AdolfEvents.NEXT)
            return self.change_location(ObchodStoleti(), send_event)

        return self

    def _start_sound4(self, send_event: SendEvent) -> None:
        """Start sound4 once, after sound3 has enabled the button."""
        if self.sound4_started:
            return

        self.sound4_started = True
        self.buttons_enabled = False
        self.phase = "sound4"
        send_event(AdolfEvents.SOUND4)

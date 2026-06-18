from enum import Enum

from interfaces import Location, SendEvent


class TricetValkaEvents(str, Enum):
    """Event ids used by the Tricet Valka location."""

    VIDEO1 = "tricet_valka_video1"
    VIDEO1_OFF = "tricet_valka_video1_off"
    VIDEO2 = "tricet_valka_video2"
    VIDEO2_OFF = "tricet_valka_video2_off"
    SOUND3 = "tricet_valka_sound3"
    SOUND3_OFF = "tricet_valka_sound3_off"
    MUSIC_LOOP = "tricet_valka_music_loop"
    MUSIC_LOOP_OFF = "tricet_valka_music_loop_off"
    TLACITKO1 = "tricet_valka_tlacitko1"
    TLACITKO2 = "tricet_valka_tlacitko2"
    SOUND4 = "tricet_valka_sound4"
    SOUND4_OFF = "tricet_valka_sound4_off"
    NEXT = "tricet_next"


class TricetValka(Location):
    """Stanoviste Tricetileta Valka."""

    name = "Tricetileta Valka"
    config_id = "tricet_valka"

    def enter_location(self, send_event: SendEvent):
        """Initialize button timing and start introductory media."""
        self.buttons_enabled = False
        self.tlacitko1_pressed = False
        self.tlacitko2_pressed = False
        self.sound4_started = False
        self.phase = "video1"
        send_event(TricetValkaEvents.VIDEO1)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id in (TricetValkaEvents.VIDEO1_OFF, TricetValkaEvents.VIDEO2_OFF):
            self._handle_video_finished(event_id, send_event)

        if event_id in (TricetValkaEvents.SOUND3_OFF, TricetValkaEvents.SOUND4_OFF):
            self._handle_sound_finished(event_id, send_event)

        if event_id == TricetValkaEvents.MUSIC_LOOP_OFF and self.phase == "music_loop":
            send_event(TricetValkaEvents.MUSIC_LOOP)

        if event_id == TricetValkaEvents.TLACITKO1 and self.buttons_enabled:
            self.tlacitko1_pressed = True
            self._start_sound4_if_ready(send_event)

        if event_id == TricetValkaEvents.TLACITKO2 and self.buttons_enabled:
            self.tlacitko2_pressed = True
            self._start_sound4_if_ready(send_event)

        if event_id == TricetValkaEvents.NEXT:
            from locations import Adolf

            return self.change_location(Adolf(), send_event)

        return self

    def _handle_video_finished(self, event_id: str, send_event: SendEvent) -> None:
        """Advance after a video end message."""
        if event_id == TricetValkaEvents.VIDEO1_OFF and self.phase == "video1":
            self.phase = "video2"
            send_event(TricetValkaEvents.VIDEO2)
        elif event_id == TricetValkaEvents.VIDEO2_OFF and self.phase == "video2":
            self.phase = "sound3"
            send_event(TricetValkaEvents.SOUND3)

    def _handle_sound_finished(self, event_id: str, send_event: SendEvent) -> None:
        """Advance after a sound end message."""
        if event_id == TricetValkaEvents.SOUND3_OFF and self.phase == "sound3":
            self.phase = "music_loop"
            self.buttons_enabled = True
            send_event(TricetValkaEvents.MUSIC_LOOP)
        elif event_id == TricetValkaEvents.SOUND4_OFF and self.phase == "sound4":
            send_event(TricetValkaEvents.NEXT)

    def _start_sound4_if_ready(self, send_event: SendEvent) -> None:
        """Start sound4 once both buttons have been pressed."""
        if self.sound4_started:
            return

        if not self.tlacitko1_pressed or not self.tlacitko2_pressed:
            return

        self.sound4_started = True
        self.buttons_enabled = False
        self.phase = "sound4"
        send_event(TricetValkaEvents.SOUND4)

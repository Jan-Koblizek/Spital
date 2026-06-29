from enum import Enum
from time import monotonic

from interfaces import Location, SendEvent


class TricetValkaEvents(str, Enum):
    """Event ids used by the Tricet Valka location."""

    SOUND1 = "tricet_valka_zvuk1"
    SOUND1_OFF = "tricet_valka_zvuk1_off"
    VIDEO1 = "tricet_valka_video1"
    VIDEO1_OFF = "tricet_valka_video1_off"
    SOUND2 = "tricet_valka_zvuk2"
    SOUND2_OFF = "tricet_valka_zvuk2_off"
    SOUND3 = "tricet_valka_sound3"
    SOUND3_OFF = "tricet_valka_sound3_off"
    MUSIC_LOOP = "tricet_valka_music_loop"
    MUSIC_LOOP_OFF = "tricet_valka_music_loop_off"
    TLACITKO1 = "tricet_valka_tlacitko1"
    TLACITKO2 = "tricet_valka_tlacitko2"
    SOUND5 = "tricet_valka_sound5"
    SOUND5_OFF = "tricet_valka_sound5_off"
    NEXT = "tricet_next"


class TricetValka(Location):
    """Stanoviste Tricetileta Valka."""

    name = "Tricetileta Valka"
    config_id = "tricet_valka"
    button_window_seconds = 2.0

    def enter_location(self, send_event: SendEvent):
        """Initialize button timing and start introductory media."""
        self.buttons_enabled = False
        self.tlacitko1_pressed_at = None
        self.tlacitko2_pressed_at = None
        self.sound5_started = False
        self.phase = "sound1"
        send_event(TricetValkaEvents.SOUND1)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == TricetValkaEvents.VIDEO1_OFF:
            self._handle_video_finished(event_id, send_event)

        if event_id in (
            TricetValkaEvents.SOUND1_OFF, 
            TricetValkaEvents.SOUND2_OFF,
            TricetValkaEvents.SOUND3_OFF,
            TricetValkaEvents.SOUND5_OFF
        ):
            self._handle_sound_finished(event_id, send_event)

        if event_id == TricetValkaEvents.MUSIC_LOOP_OFF and self.phase == "music_loop":
            send_event(TricetValkaEvents.MUSIC_LOOP)

        if event_id == TricetValkaEvents.TLACITKO1 and self.buttons_enabled:
            self.tlacitko1_pressed_at = monotonic()
            self._start_sound5_if_ready(send_event)
        elif event_id == TricetValkaEvents.TLACITKO1:
            print(f"Ignored {event_id}: buttons are disabled in phase {self.phase}.")

        if event_id == TricetValkaEvents.TLACITKO2 and self.buttons_enabled:
            self.tlacitko2_pressed_at = monotonic()
            self._start_sound5_if_ready(send_event)
        elif event_id == TricetValkaEvents.TLACITKO2:
            print(f"Ignored {event_id}: buttons are disabled in phase {self.phase}.")

        if event_id == TricetValkaEvents.NEXT:
            from locations import Adolf

            return self.change_location(Adolf(), send_event)

        return self

    def _handle_video_finished(self, event_id: str, send_event: SendEvent) -> None:
        """Advance after a video end message."""
        if event_id == TricetValkaEvents.VIDEO1_OFF and self.phase == "video1":
            self.phase = "sound2"
            send_event(TricetValkaEvents.SOUND2)

    def _handle_sound_finished(self, event_id: str, send_event: SendEvent) -> None:
        """Advance after a sound end message."""
        if event_id == TricetValkaEvents.SOUND1_OFF and self.phase == "sound1":
            self.phase = "video1"
            send_event(TricetValkaEvents.VIDEO1)
        elif event_id == TricetValkaEvents.SOUND2_OFF and self.phase == "sound2":
            self.phase = "sound3"
            send_event(TricetValkaEvents.SOUND3)
        if event_id == TricetValkaEvents.SOUND3_OFF:
            if self.phase != "sound3":
                print(f"Ignored {event_id}: expected phase sound3, got {self.phase}.")
                return

            self._enable_buttons(send_event)
        elif event_id == TricetValkaEvents.SOUND5_OFF and self.phase == "sound5":
            print("Sound5 finished, advancing to next location.")
            send_event(TricetValkaEvents.NEXT)

    def _enable_buttons(self, send_event: SendEvent) -> None:
        """Enable the two-button puzzle after sound3 finishes."""
        self.phase = "music_loop"
        self.buttons_enabled = True
        self.tlacitko1_pressed_at = None
        self.tlacitko2_pressed_at = None
        send_event(TricetValkaEvents.MUSIC_LOOP)

    def _start_sound5_if_ready(self, send_event: SendEvent) -> None:
        """Start sound5 once both buttons have been pressed close together."""
        if self.sound5_started:
            return

        if self.tlacitko1_pressed_at is None or self.tlacitko2_pressed_at is None:
            return

        time_between_presses = abs(self.tlacitko1_pressed_at - self.tlacitko2_pressed_at)

        if time_between_presses > self.button_window_seconds:
            return

        self.sound5_started = True
        self.buttons_enabled = False
        self.phase = "sound5"
        send_event(TricetValkaEvents.SOUND5)

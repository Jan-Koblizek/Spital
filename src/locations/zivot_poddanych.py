from enum import Enum

from interfaces import Location, SendEvent


class ZivotPoddanychEvents(str, Enum):
    """Event ids used by the Zivot Poddanych location."""

    SOUND1 = "zivot_poddanych_sound1"
    SOUND1_OFF = "zivot_poddanych_sound1_off"
    MUSIC_LOOP = "zivot_poddanych_music_loop"
    MUSIC_LOOP_OFF = "zivot_poddanych_music_loop_off"
    TLACITKO1 = "zivot_poddanych_tlacitko1"
    TLACITKO2 = "zivot_poddanych_tlacitko2"
    TLACITKO3 = "zivot_poddanych_tlacitko3"
    TLACITKO4 = "zivot_poddanych_tlacitko4"
    TLACITKO5 = "zivot_poddanych_tlacitko5"
    TLACITKO6 = "zivot_poddanych_tlacitko6"
    TLACITKO7 = "zivot_poddanych_tlacitko7"
    SOUND2 = "zivot_poddanych_sound2"
    SOUND2_OFF = "zivot_poddanych_sound2_off"
    SOUND3 = "zivot_poddanych_sound3"
    SOUND3_OFF = "zivot_poddanych_sound3_off"
    NEXT = "zivot_poddanych_next"


class ZivotPoddanych(Location):
    """Stanoviste Zivot Poddanych."""

    name = "Zivot Poddanych"
    config_id = "zivot_poddanych"
    required_buttons = {
        ZivotPoddanychEvents.TLACITKO1,
        ZivotPoddanychEvents.TLACITKO2,
        ZivotPoddanychEvents.TLACITKO3,
        ZivotPoddanychEvents.TLACITKO4,
        ZivotPoddanychEvents.TLACITKO5,
        ZivotPoddanychEvents.TLACITKO6,
        ZivotPoddanychEvents.TLACITKO7,
    }

    def enter_location(self, send_event: SendEvent):
        """Start the Zivot Poddanych scene."""
        self.buttons_enabled = False
        self.pressed_buttons = set()
        self.sound2_started = False
        self.phase = "sound1"
        send_event(ZivotPoddanychEvents.SOUND1)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == ZivotPoddanychEvents.SOUND1_OFF and self.phase == "sound1":
            self.phase = "music_loop"
            self.buttons_enabled = True
            send_event(ZivotPoddanychEvents.MUSIC_LOOP)

        if event_id == ZivotPoddanychEvents.MUSIC_LOOP_OFF and self.phase == "music_loop":
            send_event(ZivotPoddanychEvents.MUSIC_LOOP)

        if event_id in self.required_buttons and self.buttons_enabled:
            self.pressed_buttons.add(event_id)
            self._start_sound2_if_ready(send_event)

        if event_id == ZivotPoddanychEvents.SOUND2_OFF and self.phase == "sound2":
            self.phase = "sound3"
            send_event(ZivotPoddanychEvents.SOUND3)

        if event_id == ZivotPoddanychEvents.SOUND3_OFF and self.phase == "sound3":
            from locations import SinPredku

            send_event(ZivotPoddanychEvents.NEXT)
            return self.change_location(SinPredku(), send_event)

        return self

    def _start_sound2_if_ready(self, send_event: SendEvent) -> None:
        """Start the finale once every required button has been pressed."""
        if self.sound2_started:
            return

        if self.pressed_buttons != self.required_buttons:
            return

        self.sound2_started = True
        self.buttons_enabled = False
        self.phase = "sound2"
        send_event(ZivotPoddanychEvents.SOUND2)

from enum import Enum

from interfaces import Location, SendEvent


class ZivotPoddanychEvents(str, Enum):
    """Event ids used by the Zivot Poddanych location."""

    SOUND1 = "zivot_poddanych_sound1"
    SOUND1_OFF = "zivot_poddanych_sound1_off"
    MUSIC_LOOP = "zivot_poddanych_music_loop"
    MUSIC_LOOP_OFF = "zivot_poddanych_music_loop_off"
    TLACITKO = "zivot_poddanych_tlacitko"
    SOUND2 = "zivot_poddanych_sound2"
    SOUND2_OFF = "zivot_poddanych_sound2_off"
    SOUND3 = "zivot_poddanych_sound3"
    SOUND3_OFF = "zivot_poddanych_sound3_off"
    NEXT = "zivot_poddanych_next"


class ZivotPoddanych(Location):
    """Stanoviste Zivot Poddanych."""

    name = "Zivot Poddanych"
    config_id = "zivot_poddanych"

    def enter_location(self, send_event: SendEvent):
        """Start the Zivot Poddanych scene."""
        self.buttons_enabled = False
        self.sound2_started = False
        self.phase = "sound1"


    def enter_location(self, send_event: SendEvent):
        """Start the Zivot Poddanych scene."""
        self.buttons_enabled = False
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

        if event_id == ZivotPoddanychEvents.TLACITKO and self.buttons_enabled:
            self.sound2_started = True
            self.buttons_enabled = False
            self.phase = "sound2"
            send_event(ZivotPoddanychEvents.SOUND2)

        if event_id == ZivotPoddanychEvents.SOUND2_OFF and self.phase == "sound2":
            from locations import SinPredku
            send_event(ZivotPoddanychEvents.NEXT)
            return self.change_location(SinPredku(), send_event)

        return self

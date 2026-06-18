from enum import Enum

from interfaces import Location, SendEvent


class ObchodStoletiEvents(str, Enum):
    """Event ids used by the Obchod Stoleti location."""

    VIDEO1 = "obchod_stoleti_video1"
    VIDEO1_OFF = "obchod_stoleti_video1_off"
    SOUND2 = "obchod_stoleti_sound2"
    SOUND2_OFF = "obchod_stoleti_sound2_off"
    MUSIC_LOOP = "obchod_stoleti_music_loop"
    MUSIC_LOOP_OFF = "obchod_stoleti_music_loop_off"
    TLACITKO1 = "obchod_stoleti_tlacitko1"
    SOUND4 = "obchod_stoleti_sound4"
    SOUND4_OFF = "obchod_stoleti_sound4_off"
    NEXT = "obchod_stoleti_next"


class ObchodStoleti(Location):
    """Stanoviste Obchod Stoleti."""

    name = "Obchod Stoleti"
    config_id = "obchod_stoleti"

    def enter_location(self, send_event: SendEvent):
        """Start the Obchod Stoleti scene."""
        self.buttons_enabled = False
        self.sound4_started = False
        self.phase = "video1"
        send_event(ObchodStoletiEvents.VIDEO1)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == ObchodStoletiEvents.VIDEO1_OFF and self.phase == "video1":
            self.phase = "sound2"
            send_event(ObchodStoletiEvents.SOUND2)

        if event_id == ObchodStoletiEvents.SOUND2_OFF and self.phase == "sound2":
            self.phase = "music_loop"
            self.buttons_enabled = True
            send_event(ObchodStoletiEvents.MUSIC_LOOP)

        if event_id == ObchodStoletiEvents.MUSIC_LOOP_OFF and self.phase == "music_loop":
            send_event(ObchodStoletiEvents.MUSIC_LOOP)

        if event_id == ObchodStoletiEvents.TLACITKO1 and self.buttons_enabled:
            self._start_sound4(send_event)

        if event_id == ObchodStoletiEvents.SOUND4_OFF and self.phase == "sound4":
            from locations import ZalozeniSpitalu

            send_event(ObchodStoletiEvents.NEXT)
            return self.change_location(ZalozeniSpitalu(), send_event)

        return self

    def _start_sound4(self, send_event: SendEvent) -> None:
        """Start sound4 once after the Obchod Stoleti button is pressed."""
        if self.sound4_started:
            return

        self.sound4_started = True
        self.buttons_enabled = False
        self.phase = "sound4"
        send_event(ObchodStoletiEvents.SOUND4)

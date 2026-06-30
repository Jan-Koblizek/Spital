from enum import Enum
from threading import Timer

from interfaces import Location, SendEvent


class ZalozeniSpitaluEvents(str, Enum):
    """Event ids used by the Zalozeni Spitalu location."""

    VIDEO1 = "zalozeni_spitalu_video1"
    VIDEO1_OFF = "zalozeni_spitalu_video1_off"
    SOUND1 = "zalozeni_spitalu_sound1"
    SOUND1_OFF = "zalozeni_spitalu_sound1_off"
    MUSIC_LOOP = "zalozeni_spitalu_music_loop"
    MUSIC_LOOP_OFF = "zalozeni_spitalu_music_loop_off"
    TLACITKO1 = "zalozeni_spitalu_tlacitko1"
    SOUND2 = "zalozeni_spitalu_sound2"
    SOUND2_OFF = "zalozeni_spitalu_sound2_off"
    MUSIC_LOOP2 = "zalozeni_spitalu_music_loop2"
    MUSIC_LOOP2_OFF = "zalozeni_spitalu_music_loop2_off"
    TLACITKO2 = "zalozeni_spitalu_tlacitko2"
    NEXT = "zalozeni_spitalu_next"


class ZalozeniSpitalu(Location):
    """Stanoviste Zalozeni Spitalu."""

    name = "Zalozeni Spitalu"
    config_id = "zalozeni_spitalu"

    def enter_location(self, send_event: SendEvent):
        """Start the Zalozeni Spitalu scene with video1."""
        self.buttons_enabled = False
        self.tlacitko2_enabled = False
        self.sound2_started = False
        self.next_started = False
        self.phase = "video1"
        send_event(ZalozeniSpitaluEvents.VIDEO1)
        send_event(ZalozeniSpitaluEvents.SOUND1)

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == ZalozeniSpitaluEvents.SOUND1_OFF and self.phase == "video1":
            self.phase = "music_loop"
            self.buttons_enabled = True
            send_event(ZalozeniSpitaluEvents.MUSIC_LOOP)

        if event_id == ZalozeniSpitaluEvents.MUSIC_LOOP_OFF and self.phase == "music_loop":
            send_event(ZalozeniSpitaluEvents.MUSIC_LOOP)

        if event_id == ZalozeniSpitaluEvents.TLACITKO1 and self.buttons_enabled:
            self._start_sound2(send_event)

        if event_id == ZalozeniSpitaluEvents.SOUND2_OFF and self.phase == "sound2":
            self.phase = "music_loop2"
            send_event(ZalozeniSpitaluEvents.MUSIC_LOOP2)

        if event_id == ZalozeniSpitaluEvents.MUSIC_LOOP2_OFF and self.phase == "music_loop2":
            send_event(ZalozeniSpitaluEvents.MUSIC_LOOP2)

        if event_id == ZalozeniSpitaluEvents.TLACITKO2 and self.tlacitko2_enabled:
            from locations import Jerab

            send_event(ZalozeniSpitaluEvents.NEXT)
            return self.change_location(Jerab(), send_event)

        return self

    def _start_sound2(self, send_event: SendEvent) -> None:
        """Start sound2 once after the first button is pressed."""
        if self.sound2_started:
            return

        self.sound2_started = True
        self.buttons_enabled = False
        Timer(2, self._enable_tlacitko2).start()
        self.phase = "sound2"
        send_event(ZalozeniSpitaluEvents.SOUND2)

    def _enable_tlacitko2(self) -> None:
        self.tlacitko2_enabled = True

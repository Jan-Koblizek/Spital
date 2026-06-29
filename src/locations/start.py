from enum import Enum
from threading import Timer

from device_state import DeviceStateChecks
from interfaces import Location, SendEvent


class StartEvents(str, Enum):
    INIT = "init"
    KONTROLA = "kontrola"
    START_MP3 = "start_wav"
    START_MP3_OFF = "start_mp3_off"
    START_LIGHTS = "start_lights"
    NEXT = "start_next"
    START = "tour_start"


class Start(Location):
    name = "Pred Prohlidkou"
    config_id = "start"

    def enter_location(self, send_event: SendEvent):
        """Initialize the location and run the initial device-state check."""
        self.zkontrolovano = self._check_initial_state(send_event)
        self.start_sequence_started = False
        self.start_lights_started = False

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location."""
        if event_id == StartEvents.KONTROLA:
            self.zkontrolovano = self._check_initial_state(send_event)

        if event_id == StartEvents.START and self.zkontrolovano:
            self._start_intro_sequence(send_event)

        if event_id == StartEvents.START_MP3_OFF and self.start_sequence_started and not self.start_lights_started:
            self.start_lights_started = True
            send_event(StartEvents.START_LIGHTS)
            Timer(5, lambda: send_event(StartEvents.NEXT)).start()

        if event_id == StartEvents.NEXT:
            from locations import TricetValka

            return self.change_location(TricetValka(), send_event)

        return self

    def _check_initial_state(self, send_event: SendEvent) -> bool:
        """Ask devices for state and wait for their configured responses."""
        return DeviceStateChecks.check(lambda: send_event(StartEvents.KONTROLA))

    def _start_intro_sequence(self, send_event: SendEvent) -> None:
        """Start the pre-tour media sequence once."""
        if self.start_sequence_started:
            return

        self.start_sequence_started = True
        send_event(StartEvents.START_MP3)

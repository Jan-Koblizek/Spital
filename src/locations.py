"""List of all locations - can be separated into more files if desired."""

from datetime import datetime
from enum import Enum
from threading import Timer

from interfaces import Location, SendEvent
from device_state import DeviceStateChecks
        
        
class StartEvents(str, Enum):
    INIT = "init"
    KONTROLA = "kontrola"
    START = "tour_start"
    
    
class Start(Location):
    
    name = "Před Prohlídkou"
    config_id = "start"
    
    def enter_location(self, send_event: SendEvent):
        """Initialize the location, perfomr checks"""
        self.zkontrolovano = False
        send_event(StartEvents.KONTROLA)
    
    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location.

        Args:
            event_id (str): id of the event we are reacting to
            payload (str | None): decoded event payload
            send_event (SendEvent): function that can be used to send event

        Returns:
            Location: new location (or self if location didn't change)
        """
        if event_id == StartEvents.KONTROLA:
            self.zkontrolovano = DeviceStateChecks.check()
        if event_id == StartEvents.START and self.zkontrolovano:
            return self.change_location(TricetValka(), send_event)
        return self
    


class TricetValkaEvents(str, Enum):
    """Event ids used by the Tricet Valka location.

    Values must match ids from `event_configs/tricet_valka.json`.
    """

    TLACITKO1 = "tricet_valka_tlacitko1"
    TLACITKO2 = "tricet_valka_tlacitko2"
    VALKA_UV = "30_valka_uv"
    VALKA_UV_OFF = "30_valka_uv_off"
    MP3 = "tricet_valka_mp3"
    MP3_2 = "tricet_valka_mp3_2"
    MP3_3 = "tricet_valka_mp3_3"
    VIDEO = "tricet_valka_video"
    BRIGHTNESS = "tricet_valka_brightness"
    RGB = "tricet_valka_rgb"
    BRIGHTNESS_OFF = "tricet_valka_brightness_off"
    RGB_OFF = "tricet_valka_rgb_off"
    TOUR_START = "tour_start"
    NEXT = "tricet_next"


class TricetValka(Location):
    """Tricetileta Valka location behavior."""
    
    name = "Tricetileta Valka"
    config_id = "tricet_valka"
    
    def enter_location(self, send_event: SendEvent):
        """Initialize button timing and start introductory media."""
        self.tlacitko1_time = datetime.fromtimestamp(0)
        self.tlacitko2_time = datetime.fromtimestamp(0)
        send_event(TricetValkaEvents.MP3)
        Timer(180, lambda: send_event(TricetValkaEvents.VIDEO)).start()
        
    def final_sequence(self, send_event: SendEvent):
        """Run the output sequence that leads to the next location."""
        # TODO: Could probably be defined as a single event
        send_event(TricetValkaEvents.VALKA_UV_OFF)
        send_event(TricetValkaEvents.BRIGHTNESS)
        send_event(TricetValkaEvents.RGB)
        send_event(TricetValkaEvents.MP3_2)
        Timer(20, lambda: send_event(TricetValkaEvents.NEXT)).start()
        
    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """React to configured events for this location.

        Args:
            event_id (str): id of the event we are reacting to
            payload (str | None): decoded event payload
            send_event (SendEvent): function that can be used to send event

        Returns:
            Location: new location (or self if location didn't change)
        """
        if event_id == TricetValkaEvents.TLACITKO1:
            self.tlacitko1_time = datetime.now()
            if (self.tlacitko1_time - self.tlacitko2_time).total_seconds() < 2:
                send_event(TricetValkaEvents.NEXT)
                
        if event_id == TricetValkaEvents.TLACITKO2:
            self.tlacitko2_time = datetime.now()
            if (self.tlacitko2_time - self.tlacitko1_time).total_seconds() < 2:
                send_event(TricetValkaEvents.NEXT)
                         
        if event_id == TricetValkaEvents.NEXT:
            print("changing locations")
            return self.change_location(Adolf(), send_event)
        
        return self

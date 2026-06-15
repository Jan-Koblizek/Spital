from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PayloadCondition:
    """Simple payload condition.

    A scalar value means exact text match. A two-number tuple means the payload
    must parse as a number inside the inclusive range.
    """
    value: str | int | float | bool | tuple[int | float, int | float]

    def matches(self, payload: str | None) -> bool:
        """Return whether a decoded payload satisfies this condition."""
        if payload is None:
            return False

        if isinstance(self.value, tuple):
            return self._matches_range(payload)

        return payload == str(self.value)

    def _matches_range(self, payload: str) -> bool:
        """Return whether a decoded payload is inside this numeric range."""
        minimum, maximum = self.value

        try:
            value = float(payload)
        except ValueError:
            return False

        return minimum <= value <= maximum


@dataclass(frozen=True)
class EventMessage:
    """One MQTT message that should be published for an event."""
    topic: str
    payload: bytes | None = None
    delay: float = 0.0

    def to_dict(self) -> dict[str, str | float | None]:
        """Return a frontend-safe representation of this MQTT message."""
        return {
            "topic": self.topic,
            "payload": self.payload.decode("utf-8") if self.payload is not None else None,
            "delay": self.delay,
        }


@dataclass(frozen=True)
class Event:
    """Configured event definition or concrete event instance.

    Event definitions come from `event_configs/*.json`. Runtime code may attach
    a concrete payload to a definition with `with_payload`.
    """
    id: str                 # Event identifier
    name: str               # Human readable name of the event
    topic: str              # Topic the event uses
    description: str        # Description of the event (maybe it could be displayed somewhere)
    payload: bytes | None = None    # The message associated with the event
    conditions: tuple[PayloadCondition, ...] = ()
    messages: tuple[EventMessage, ...] = ()
    incoming: bool = True           # Whether incoming MQTT messages can trigger this event

    def with_payload(self, payload: bytes | None) -> Event:
        """Return this event definition with a concrete payload."""
        return Event(
            id=self.id,
            name=self.name,
            topic=self.topic,
            description=self.description,
            payload=payload,
            conditions=self.conditions,
            messages=self.messages,
            incoming=self.incoming,
        )

    def conditions_match(self, payload: str | None) -> bool:
        """Return whether all configured conditions allow this event."""
        return all(condition.matches(payload) for condition in self.conditions)

    def outbound_messages(self) -> tuple[EventMessage, ...]:
        """Return MQTT messages that should be published for this event."""
        if self.messages:
            return self.messages

        if not self.topic:
            return ()

        return (EventMessage(topic=self.topic, payload=self.payload),)

    def to_dict(self) -> dict[str, object]:
        """Return a frontend-safe representation of the event."""
        return {
            "id": self.id,
            "name": self.name,
            "topic": self.topic,
            "description": self.description,
            "has_payload": any(message.payload is not None for message in self.outbound_messages()),
            "messages": [
                message.to_dict()
                for message in self.outbound_messages()
            ],
        }
    

SendEvent = Callable[[Event | str], None]     # Function that can be used to send an Event to connected devices


class Location:
    """One location in the escape room.
    
    Caution is advised. We must always clearly know where the players are located.
    This would mean physically separated rooms or clear entries to new locations.
    Players cannot be in two locations at once or none at all.
    """
    
    name: str
    config_id: str | None = None

    def process_event(
        self,
        event_id: str,
        payload: str | None,
        send_event: SendEvent,
    ) -> Location:
        """Event coming from the real world. If relevant, process it.
        
        Args:
            event_id (str): id of the event we are reacting to
            payload (str | None): decoded event payload
            send_event (SendEvent): object we can use to publish our own Events
        """
        return self
    
    def change_location(self, new: Location, send_event: SendEvent) -> Location:
        """Switch to another location.
        
        Calls exit_location for the old and enter_location for the new location.
        
        Arguments:
            new (Location): location the players will move to.
        """
        self.exit_location(send_event)
        new.enter_location(send_event)
        return new
    
    def enter_location(self, send_event: SendEvent):
        """Run setup logic when players enter this location."""
        return None
        
    def exit_location(self, send_event: SendEvent):
        """Run cleanup logic when players leave this location."""
        return None

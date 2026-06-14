"""Runtime state and behavior for the Escape Room."""

from __future__ import annotations

from queue import Queue
from threading import Lock, Thread, current_thread
from typing import Callable, TypeAlias

from event_config import EVENTS_BY_ID, EVENT_IDS_BY_LOCATION, EVENTS_BY_TOPIC
from interfaces import Event, Location, SendEvent


RuntimeMessageType: TypeAlias = tuple[str, str | None] | Event | None
"""Message queued for the runtime worker thread."""

RuntimeFinishedHandler: TypeAlias = Callable[[str], None]
"""Callback invoked when a runtime reaches a terminal location."""

OutboundEventSender: TypeAlias = Callable[[Event], None]
"""Sends a resolved event to the outside world."""



class EscapeRoomRuntime:
    """State machine for one active group moving through locations."""

    def __init__(
        self,
        runtime_id: str,
        name: str,
        start_location: Location,
        send_event: OutboundEventSender,
        finished_handler: RuntimeFinishedHandler | None = None,
    ):
        """Initialize one runtime instance with its starting location."""
        self._lock = Lock()
        self._messages: Queue[RuntimeMessageType] = Queue()
        self._thread: Thread | None = None
        self._running = False
        self.id = runtime_id
        self.name = name
        self.current_location = start_location
        self.send_event = send_event
        self.finished_handler = finished_handler

    @property
    def current_location_name(self) -> str:
        """Human readable name of the current location."""
        with self._lock:
            return self.current_location.name

    def state(self) -> dict[str, object]:
        """Snapshot of runtime state for observers such as the frontend."""
        with self._lock:
            location = self.current_location
            event_ids = self._available_event_ids(location)
            location_variables = self._location_variables(location)

        return {
            "id": self.id,
            "name": self.name,
            "current_location_name": location.name,
            "location_variables": location_variables,
            "events": [
                EVENTS_BY_ID[event_id].to_dict()
                for event_id in event_ids
                if event_id in EVENTS_BY_ID
            ],
        }

    def start(self) -> None:
        """Start the runtime without blocking the application main loop."""
        if self._running:
            return

        self._running = True
        self._thread = Thread(target=self._run, daemon=True)
        self.current_location.enter_location(self._send_event)
        self._thread.start()

    def stop(self) -> None:
        """Stop the runtime."""
        if not self._running:
            return

        self._running = False
        self._messages.put(None)
        if self._thread is not None and self._thread is not current_thread():
            self._thread.join(timeout=5)
            self._thread = None

    def handle_message(self, topic: str, payload: str | None) -> None:
        """Queue an incoming message so processing cannot block the caller.

        Args:
            topic (str): topic this is coming from
            payload (str | None): decoded message payload
        """
        self._messages.put((topic, payload))

    def trigger_event(self, event_id: str) -> bool:
        """Queue a configured event by id if it is available here."""
        with self._lock:
            event_ids = self._available_event_ids(self.current_location)

        if event_id not in event_ids:
            return False

        event_definition = EVENTS_BY_ID.get(event_id)

        if event_definition is None:
            return False

        self.handle_event(event_definition.with_payload(event_definition.payload))
        return True

    def handle_event(self, event: Event) -> None:
        """Queue an already resolved event."""
        self._messages.put(event)

    def _available_event_ids(self, location: Location) -> list[str]:
        """Return event ids configured for a location's `config_id`."""
        if location.config_id is None:
            return []

        return EVENT_IDS_BY_LOCATION.get(location.config_id, [])

    def _location_variables(self, location: Location) -> dict[str, object]:
        """Return public location variables that can be displayed in the UI."""
        variables: dict[str, object] = {}

        for name, value in vars(location).items():
            if name.startswith("_"):
                continue

            if isinstance(value, str | int | float | bool) or value is None:
                variables[name] = value
            else:
                variables[name] = repr(value)

        return variables

    def _run(self) -> None:
        """Process queued messages until stopped or the runtime finishes."""
        while True:
            message = self._messages.get()

            if message is None:
                return

            if isinstance(message, Event):
                if self._process_event(message):
                    return
                continue

            topic, payload = message
            if self._process_message(topic, payload):
                return

    def _process_message(self, topic: str, payload: str | None) -> bool:
        """Resolve an incoming topic/payload to an event and apply it."""
        event_definition = self._event_for_message(topic, payload)

        if event_definition is None:
            print(f"Unknown MQTT topic: {topic}")
            return False

        return self._apply_event(event_definition, payload)

    def _event_for_message(self, topic: str, payload: str | None) -> Event | None:
        """Choose the first event matching topic, location, and condition."""
        events = EVENTS_BY_TOPIC.get(topic, [])

        if not events:
            return None

        with self._lock:
            event_ids = set(self._available_event_ids(self.current_location))

        for event in events:
            if event.id not in event_ids:
                continue

            if event.conditions_match(payload):
                return event

        print(f"No matching event for topic: {topic}")
        return None

    def _process_event(self, event: Event) -> bool:
        """Apply an already resolved event with its configured payload."""
        payload = self._decode_payload(event.payload)

        if not event.conditions_match(payload):
            print(f"\nIgnored event: {event.name}")
            print(f"Payload did not match configured conditions: {payload}")
            return False

        return self._apply_event(event, payload)

    def _apply_event(self, event: Event, payload: str | None) -> bool:
        """Run location logic for an event and return whether runtime ended."""
        finished = False

        with self._lock:
            print(f"\nReceived event: {event.name}")

            self.current_location = self.current_location.process_event(
                event.id,
                payload,
                self._send_event,
            )

            print(f"Location after: {self.current_location.name}")
            finished = self.current_location.config_id is None

        if finished:
            self._running = False
            print(f"Runtime finished: {self.id}")

            if self.finished_handler is not None:
                self.finished_handler(self.id)

            return True

        return False

    def _decode_payload(self, payload: bytes | None) -> str | None:
        if payload is None:
            return None

        return payload.decode("utf-8")

    def _send_event(self, event: Event | str) -> None:
        """Send an outbound event, resolving string event ids for location code."""
        if isinstance(event, str):
            event_definition = EVENTS_BY_ID.get(event)

            if event_definition is None:
                print(f"Unknown event id: {event}")
                return

            self.send_event(event_definition)
            return

        self.send_event(event)

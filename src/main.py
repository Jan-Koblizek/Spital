"""Application entrypoint."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from time import sleep

from communicator import Communicator
from config import device_state_config
from device_state import DeviceStateChecker, DeviceStateChecks, load_device_state_definition
from event_config import EVENTS_BY_ID, EVENTS_BY_TOPIC, reload_events
from frontend_server import FrontendServer
from locations import *
from interfaces import Event
from runtime import EscapeRoomRuntime, OutboundEventSender


# Tour wiring: change these when the tour starts or ends somewhere else.
START_EVENT_ID = StartEvents.INIT
START_LOCATION = Start
END_EVENT_IDS = {
    TricetValkaEvents.NEXT,
}

RUNTIME_CREATE_COOLDOWN = timedelta(minutes=1)


def main() -> None:
    """Start MQTT, frontend API, device-state checks, and runtime manager."""
    device_state_definition = load_device_state_definition()
    device_state_checker = (
        DeviceStateChecker(device_state_definition)
        if device_state_definition is not None
        else None
    )
    runtime_manager = RuntimeManager(lambda event: communicator.send_event(event))
    communicator = Communicator(
        lambda topic, payload: handle_message(runtime_manager, device_state_checker, topic, payload)
    )
    DeviceStateChecks.configure(lambda: execute_device_state_check(communicator, device_state_checker))

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    frontend = FrontendServer(
        frontend_dir,
        lambda: runtime_manager.state(device_state_checker),
        runtime_manager.trigger_runtime_event,
        runtime_manager.trigger_start_event,
        runtime_manager.kill_runtime,
        reload_events,
    )

    communicator.start()
    check_startup_device_states(communicator, device_state_checker)

    frontend.start()
    print(f"Frontend available at {frontend.url}")

    try:
        while True:
            # Other application tasks can run here without being blocked by the runtime.
            sleep(1)
    except KeyboardInterrupt:
        print("\nStopping application.")
    finally:
        frontend.stop()
        communicator.stop()
        runtime_manager.stop_all()


def handle_message(
    runtime_manager: "RuntimeManager",
    device_state_checker: DeviceStateChecker | None,
    topic: str,
    payload: str | None,
) -> None:
    """Deliver incoming messages to startup checks and active runtimes."""
    if device_state_checker is not None:
        device_state_checker.handle_message(topic, payload)

    runtime_manager.dispatch_message(topic, payload)


def check_startup_device_states(communicator: Communicator, checker: DeviceStateChecker | None) -> None:
    """Run the startup device-state check and print its result."""
    if execute_device_state_check(communicator, checker):
        print("Device startup state check passed.")


def execute_device_state_check(communicator: Communicator, checker: DeviceStateChecker | None) -> bool:
    """Ask devices for state and return whether configured responses match."""
    if checker is None:
        print("No device state config found; skipping device state check.")
        return True

    checker.start()
    communicator.send_message(device_state_config.request_topic, device_state_config.request_payload)
    checker.wait(timeout=2)

    missing, mismatched = checker.result()

    if not missing and not mismatched:
        return True

    print("Device state check failed.")

    for expected in missing:
        print(f"Missing state: {expected.topic} expected {expected.expected_value}")

    for expected, actual in mismatched:
        print(f"Mismatched state: {expected.topic} expected {expected.expected_value}, got {actual}")

    return False


class RuntimeManager:
    """Own all active runtimes and route incoming messages to them."""

    def __init__(self, send_event: OutboundEventSender):
        """Create a manager with an outbound event hook."""
        self._lock = Lock()
        self._runtimes: list[EscapeRoomRuntime] = []
        self._last_created_at: datetime | None = None
        self._next_runtime_number = 1
        self.send_event = send_event

    def state(self, device_state_checker: DeviceStateChecker | None = None) -> dict[str, object]:
        """Return frontend state for every runtime plus the global start event."""
        with self._lock:
            runtimes = [self._runtime_state(runtime) for runtime in self._runtimes]

        start_event = EVENTS_BY_ID.get(START_EVENT_ID)
        device_state = device_state_checker.state() if device_state_checker is not None else None

        return {
            "runtimes": runtimes,
            "start_event": start_event.to_dict() if start_event is not None else None,
            "device_state": device_state,
        }

    def dispatch_message(self, topic: str, payload: str | None) -> None:
        """Create a runtime from the start event, otherwise deliver to every runtime."""
        start_event = self._start_event_for_message(topic, payload)

        if start_event is not None:
            self._create_runtime_from_message(start_event, payload)
            return

        with self._lock:
            runtimes = list(self._runtimes)

        for runtime in runtimes:
            runtime.handle_message(topic, payload)

    def _start_event_for_message(self, topic: str, payload: str | None) -> Event | None:
        """Return the configured start event if this message should start a run."""
        for event in EVENTS_BY_TOPIC.get(topic, []):
            if event.id == START_EVENT_ID and event.conditions_match(payload):
                return event

        return None

    def trigger_start_event(self, event_id: str) -> bool:
        """Trigger the configured start event from the frontend."""
        if event_id != START_EVENT_ID:
            return False

        event = EVENTS_BY_ID.get(event_id)

        if event is None:
            return False

        return self._create_runtime_from_event(event)

    def trigger_runtime_event(self, runtime_id: str, event_id: str) -> bool:
        """Trigger an event in a runtime by id."""
        if event_id == START_EVENT_ID:
            return False

        with self._lock:
            runtime = self._runtime_by_id(runtime_id)

        if runtime is None:
            return False

        return runtime.trigger_event(event_id)

    def kill_runtime(self, runtime_id: str) -> bool:
        """Stop and remove a runtime."""
        with self._lock:
            runtime = self._runtime_by_id(runtime_id)

            if runtime is None:
                return False

            self._runtimes.remove(runtime)

        runtime.stop()
        print(f"Killed runtime: {runtime_id}")
        return True

    def stop_all(self) -> None:
        """Stop every active runtime."""
        with self._lock:
            runtimes = list(self._runtimes)
            self._runtimes.clear()

        for runtime in runtimes:
            runtime.stop()

    def _create_runtime_from_event(self, event: Event) -> bool:
        """Create a runtime from a configured/frontend-triggered event."""
        payload = self._decode_payload(event.payload)
        return self._create_runtime_from_message(event, payload)

    def _create_runtime_from_message(self, event: Event, payload: str | None) -> bool:
        """Create a runtime from an incoming start message after validation."""
        if not event.conditions_match(payload):
            print(f"Ignored start event because payload did not match conditions: {payload}")
            return False

        now = datetime.now()

        with self._lock:
            if self._last_created_at is not None and now - self._last_created_at < RUNTIME_CREATE_COOLDOWN:
                print("Ignored start event because a runtime was created less than a minute ago.")
                return False

            runtime_number = self._next_runtime_number
            self._next_runtime_number += 1
            self._last_created_at = now

            runtime = EscapeRoomRuntime(
                f"runtime-{runtime_number}",
                f"Runtime {runtime_number}",
                START_LOCATION(),
                self.send_event,
                self.finish_runtime,
            )
            self._runtimes.append(runtime)

        runtime.start()
        runtime.handle_message(event.topic, payload)
        print(f"Created runtime: {runtime.id}")
        return True

    def finish_runtime(self, runtime_id: str) -> None:
        """Remove a runtime that finished from inside its own code path."""
        with self._lock:
            runtime = self._runtime_by_id(runtime_id)

            if runtime is None:
                return

            self._runtimes.remove(runtime)

        print(f"Removed finished runtime: {runtime_id}")

    def _runtime_by_id(self, runtime_id: str) -> EscapeRoomRuntime | None:
        """Find an active runtime by id."""
        for runtime in self._runtimes:
            if runtime.id == runtime_id:
                return runtime

        return None

    def _runtime_state(self, runtime: EscapeRoomRuntime) -> dict[str, object]:
        """Return frontend state without globally handled start/end events."""
        state = runtime.state()
        state["events"] = [
            event
            for event in state["events"]
            if isinstance(event, dict)
            and event.get("id") != START_EVENT_ID
            and event.get("id") not in END_EVENT_IDS
        ]
        return state

    def _decode_payload(self, payload: bytes | None) -> str | None:
        """Decode a configured event payload to text for condition checks."""
        if payload is None:
            return None

        return payload.decode("utf-8")


# Standard safeguard - only do this if called via command line
if __name__ == "__main__":
    main()

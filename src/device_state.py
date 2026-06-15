"""Device state checks driven by simple expected-value config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Event as ThreadEvent
from threading import Lock
from typing import Any, Callable, ClassVar

from config import device_state_config
from interfaces import PayloadCondition


DeviceStateRequest = Callable[[], None]
"""Function that asks devices to publish their current state."""


DeviceStateCheckExecutor = Callable[[DeviceStateRequest | None], bool]
"""Function that performs a configured device-state check."""


class DeviceStateChecks:
    """Static access point for running configured device-state checks.

    Location code passes the action that asks devices to publish their state;
    the checker only collects and validates the responses.
    """

    _executor: ClassVar[DeviceStateCheckExecutor | None] = None

    @classmethod
    def configure(cls, executor: DeviceStateCheckExecutor) -> None:
        """Install the application-level check executor."""
        cls._executor = executor

    @classmethod
    def check(cls, request_state: DeviceStateRequest | None = None) -> bool:
        """Run the configured device-state check and return whether it passed."""
        if cls._executor is None:
            print("Device state check is not configured.")
            return True

        return cls._executor(request_state)


@dataclass(frozen=True)
class ExpectedDeviceState:
    """Expected state response for one MQTT topic."""
    topic: str
    condition: PayloadCondition

    @property
    def expected_value(self) -> object:
        """Raw value displayed when the check reports failures."""
        return self.condition.value

    def matches(self, payload: str | None) -> bool:
        """Return whether the received payload satisfies the expected value."""
        return self.condition.matches(payload)


@dataclass(frozen=True)
class DeviceStateDefinition:
    """Complete set of topics that must answer during a state check."""
    expected_states: tuple[ExpectedDeviceState, ...]


@dataclass(frozen=True)
class DeviceStateIssue:
    """One missing or mismatched device state for frontend display."""
    topic: str
    expected: object
    actual: str | None
    status: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation of this issue."""
        return {
            "topic": self.topic,
            "expected": self.expected,
            "actual": self.actual,
            "status": self.status,
        }


@dataclass(frozen=True)
class DeviceStateCheckResult:
    """Result of the latest device state check."""
    passed: bool
    issues: tuple[DeviceStateIssue, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe result for the frontend."""
        return {
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def load_device_state_definition(config_dir: Path = device_state_config.directory) -> DeviceStateDefinition | None:
    """Load device state expectations from `*.json` files.

    Each file must be a JSON object mapping topic names to an expected scalar
    value or a two-number range, for example `{ "topic": "on" }`.
    """
    if not config_dir.exists():
        return None

    expected_states: list[ExpectedDeviceState] = []

    for config_path in sorted(config_dir.glob("*.json")):
        config = json.loads(config_path.read_text(encoding="utf-8"))

        expected_states.extend(_states_from_config(config))

    if not expected_states:
        return None

    return DeviceStateDefinition(expected_states=tuple(expected_states))


class DeviceStateChecker:
    """Collect and validate device state responses for one active check."""

    def __init__(self, definition: DeviceStateDefinition):
        """Prepare a checker for the loaded device state definition."""
        self.definition = definition
        self._lock = Lock()
        self._done = ThreadEvent()
        self._expected_topics = {
            state.topic
            for state in definition.expected_states
        }
        self._received: dict[str, str | None] = {}
        self._active = False
        self._last_result: DeviceStateCheckResult | None = None

    def start(self) -> None:
        """Start collecting device state messages."""
        with self._lock:
            self._received.clear()
            self._active = True
            self._done.clear()

    def handle_message(self, topic: str, payload: str | None) -> None:
        """Record an incoming state response if it is part of the check."""
        with self._lock:
            if not self._active or topic not in self._expected_topics:
                return

            self._received[topic] = payload

            if self._expected_topics <= self._received.keys():
                self._done.set()

    def wait(self, timeout: float = 2.0) -> DeviceStateCheckResult:
        """Wait for all configured states or until timeout."""
        self._done.wait(timeout)

        result = self.current_result()

        with self._lock:
            self._active = False
            self._last_result = result

        return result

    @property
    def passed(self) -> bool:
        """Return whether all expected states arrived and matched."""
        return self.current_result().passed

    def result(self) -> tuple[list[ExpectedDeviceState], list[tuple[ExpectedDeviceState, str | None]]]:
        """Return missing and mismatched states."""
        missing: list[ExpectedDeviceState] = []
        mismatched: list[tuple[ExpectedDeviceState, str | None]] = []

        with self._lock:
            received = dict(self._received)

        for expected in self.definition.expected_states:
            if expected.topic not in received:
                missing.append(expected)
                continue

            actual = received[expected.topic]

            if not expected.matches(actual):
                mismatched.append((expected, actual))

        return missing, mismatched

    def current_result(self) -> DeviceStateCheckResult:
        """Return the current check result as structured issue objects."""
        missing, mismatched = self.result()
        issues = [
            DeviceStateIssue(
                topic=expected.topic,
                expected=expected.expected_value,
                actual=None,
                status="missing",
            )
            for expected in missing
        ]
        issues.extend(
            DeviceStateIssue(
                topic=expected.topic,
                expected=expected.expected_value,
                actual=actual,
                status="mismatched",
            )
            for expected, actual in mismatched
        )

        return DeviceStateCheckResult(
            passed=not issues,
            issues=tuple(issues),
        )

    def state(self) -> dict[str, object] | None:
        """Return latest check result for frontend state."""
        with self._lock:
            result = self._last_result

        return result.to_dict() if result is not None else None


def _states_from_config(config: Any) -> list[ExpectedDeviceState]:
    """Convert one JSON object into expected device state records."""
    if not isinstance(config, dict):
        raise ValueError("Device state config must be a JSON object mapping topics to expected values.")

    return [
        _state_from_config(topic, value)
        for topic, value in config.items()
    ]


def _state_from_config(topic: str, value: Any) -> ExpectedDeviceState:
    """Convert one topic/value pair into an expected state."""
    if not isinstance(topic, str):
        raise ValueError("Device state topics must be strings.")

    if isinstance(value, list):
        if len(value) != 2:
            raise ValueError("Device state range value must have exactly two values.")

        condition = PayloadCondition(value=(float(value[0]), float(value[1])))
    else:
        condition = PayloadCondition(value=value)

    return ExpectedDeviceState(
        topic=topic,
        condition=condition,
    )

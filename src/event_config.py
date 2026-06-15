"""Load event definitions from location config files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import event_config
from interfaces import Event, EventMessage, PayloadCondition


def load_events(config_dir: Path = event_config.directory) -> dict[str, Event]:
    """Load all configured events indexed by event id."""
    events: dict[str, Event] = {}

    if not config_dir.exists():
        raise FileNotFoundError(f"Event config directory does not exist: {config_dir}")

    for config_path in sorted(config_dir.glob("*.json")):
        config = json.loads(config_path.read_text(encoding="utf-8"))

        for raw_event in config.get("events", []):
            event = _event_from_config(raw_event)

            if event.id in events:
                raise ValueError(f"Duplicate event id '{event.id}' in {config_path}")

            events[event.id] = event

    return events


def events_by_topic(events: dict[str, Event]) -> dict[str, list[Event]]:
    """Index events with MQTT topics, preserving config order for duplicates."""
    indexed_events: dict[str, list[Event]] = {}

    for event in events.values():
        for topic in _topics_for_event(event):
            indexed_events.setdefault(topic, []).append(event)

    return indexed_events


def events_by_location(config_dir: Path = event_config.directory) -> dict[str, list[str]]:
    """Load event ids indexed by location id."""
    indexed_events: dict[str, list[str]] = {}

    if not config_dir.exists():
        raise FileNotFoundError(f"Event config directory does not exist: {config_dir}")

    for config_path in sorted(config_dir.glob("*.json")):
        config = json.loads(config_path.read_text(encoding="utf-8"))
        location_id = config.get("location")

        if not location_id:
            continue

        if location_id in indexed_events:
            raise ValueError(f"Duplicate location event config '{location_id}' in {config_path}")

        indexed_events[location_id] = [
            raw_event["id"]
            for raw_event in config.get("events", [])
        ]

    return indexed_events


def reload_events() -> None:
    """Reload event config files into the existing module-level indexes.

    The dictionaries are mutated in place so existing runtime objects continue
    reading from the updated config without being recreated.
    """
    events = load_events()
    topics = events_by_topic(events)
    locations = events_by_location()

    EVENTS_BY_ID.clear()
    EVENTS_BY_ID.update(events)

    EVENTS_BY_TOPIC.clear()
    EVENTS_BY_TOPIC.update(topics)

    EVENT_IDS_BY_LOCATION.clear()
    EVENT_IDS_BY_LOCATION.update(locations)


def _event_from_config(raw_event: dict[str, Any]) -> Event:
    """Build an `Event` from one JSON event object."""
    messages = _messages_from_config(raw_event)
    first_message = messages[0] if messages else None

    return Event(
        id=raw_event["id"],
        name=raw_event["name"],
        topic=first_message.topic if first_message is not None else "",
        description=raw_event.get("description", ""),
        payload=first_message.payload if first_message is not None else None,
        conditions=_condition_from_config(raw_event.get("condition")),
        messages=messages,
        incoming=raw_event.get("incoming", True),
    )


def _messages_from_config(raw_event: dict[str, Any]) -> tuple[EventMessage, ...]:
    """Build outbound MQTT messages from topic/payload config.

    If topic and payload list lengths match, each payload is sent to the
    corresponding topic. Otherwise all payloads are sent to the first topic.
    """
    topics = _topics_from_config(raw_event.get("topic", ""))

    if not topics:
        return ()

    payloads = _payloads_from_config(raw_event.get("payload"))

    if len(topics) == len(payloads):
        return tuple(
            EventMessage(topic=topic, payload=payload, delay=delay)
            for topic, (payload, delay) in zip(topics, payloads)
        )

    return tuple(
        EventMessage(topic=topics[0], payload=payload, delay=delay)
        for payload, delay in payloads
    )


def _topics_from_config(raw_topic: Any) -> tuple[str, ...]:
    """Return configured MQTT topics."""
    if raw_topic is None or raw_topic == "":
        return ()

    if isinstance(raw_topic, str):
        return (raw_topic,)

    if isinstance(raw_topic, list) and all(isinstance(topic, str) for topic in raw_topic):
        return tuple(raw_topic)

    raise ValueError("Event topic must be a string or a list of strings.")


def _payloads_from_config(raw_payload: Any) -> tuple[tuple[bytes | None, float], ...]:
    """Return payload/delay pairs from config."""
    if _is_delayed_payload_list(raw_payload):
        return tuple(
            (_encode_payload(payload), float(delay))
            for payload, delay in raw_payload
        )

    return ((_encode_payload(raw_payload), 0.0),)


def _is_delayed_payload_list(raw_payload: Any) -> bool:
    """Return whether payload config is `[[payload, delay], ...]`."""
    return (
        isinstance(raw_payload, list)
        and all(
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[1], int | float)
            for item in raw_payload
        )
    )


def _encode_payload(payload: Any) -> bytes | None:
    """Encode a configured payload value as UTF-8 bytes."""
    if payload is None:
        return None

    return str(payload).encode("utf-8")


def _topics_for_event(event: Event) -> tuple[str, ...]:
    """Return the canonical topic that can trigger an event."""
    return (event.topic,) if event.incoming and event.topic else ()


def _condition_from_config(raw_condition: Any) -> tuple[PayloadCondition, ...]:
    """Build the optional payload condition from JSON config."""
    if raw_condition is None:
        return ()

    if isinstance(raw_condition, list):
        if len(raw_condition) != 2:
            raise ValueError("Payload range condition must have exactly two values.")

        return (PayloadCondition(value=(float(raw_condition[0]), float(raw_condition[1]))),)

    return (PayloadCondition(value=raw_condition),)


EVENTS_BY_ID = load_events()
EVENTS_BY_TOPIC = events_by_topic(EVENTS_BY_ID)
EVENT_IDS_BY_LOCATION = events_by_location()

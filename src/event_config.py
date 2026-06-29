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
    macros = load_event_macros(config_dir)

    if not config_dir.exists():
        raise FileNotFoundError(f"Event config directory does not exist: {config_dir}")

    for config_path in sorted(config_dir.glob("*.json")):
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))

        for raw_event in config.get("events", []):
            for event in _events_from_config(raw_event, macros):
                if event.id in events:
                    raise ValueError(f"Duplicate event id '{event.id}' in {config_path}")

                events[event.id] = event

    return events


def load_event_macros(config_dir: Path = event_config.directory) -> dict[str, Any]:
    """Load optional event macros shared by location configs."""
    macro_path = config_dir / "macros.json"

    if not macro_path.exists():
        return {}

    macros = json.loads(macro_path.read_text(encoding="utf-8-sig"))

    if not isinstance(macros, dict):
        raise ValueError("Event macros config must be a JSON object.")

    if "macros" in macros:
        if not isinstance(macros.get("macros"), dict):
            raise ValueError("Event macros config field 'macros' must be a JSON object.")

        if not isinstance(macros.get("lights", {}), dict):
            raise ValueError("Event macros config field 'lights' must be a JSON object.")

    return macros


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
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        location_id = config.get("location")

        if not location_id:
            continue

        if location_id in indexed_events:
            raise ValueError(f"Duplicate location event config '{location_id}' in {config_path}")

        event_ids: list[str] = []

        for raw_event in config.get("events", []):
            event_ids.append(raw_event["id"])

            if raw_event.get("media_end"):
                event_ids.append(_media_end_event_id(raw_event))

        indexed_events[location_id] = event_ids

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


def _events_from_config(raw_event: dict[str, Any], macros: dict[str, Any]) -> tuple[Event, ...]:
    """Build an event and any generated helper events from config."""
    event = _event_from_config(raw_event, macros)

    if not raw_event.get("media_end"):
        return (event,)

    return (event, _media_end_event_from_config(raw_event, macros))


def _event_from_config(raw_event: dict[str, Any], macros: dict[str, Any]) -> Event:
    """Build an `Event` from one JSON event object."""
    messages = _messages_from_config(raw_event, macros)
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


def _media_end_event_from_config(raw_event: dict[str, Any], macros: dict[str, Any]) -> Event:
    """Build the generated event fired when media playback ends."""
    media_end_topic = macros.get("media_status_topic", macros.get("media_end_topic"))

    if not isinstance(media_end_topic, str) or not media_end_topic:
        raise ValueError("Media end events require 'media_status_topic' in event_configs/macros.json.")

    event_id = _media_end_event_id(raw_event)
    payload = _media_end_payload(raw_event)
    messages = _media_stop_messages_from_config(raw_event)

    return Event(
        id=event_id,
        name=f"{raw_event.get('name', raw_event['id'])} - konec",
        topic=media_end_topic,
        description=f"Generated media end event for {raw_event['id']}.",
        payload=_encode_payload(payload),
        conditions=(PayloadCondition(value=payload),),
        messages=messages,
        incoming=True,
    )


def _media_end_payload(raw_event: dict[str, Any]) -> str:
    """Return the media status id that marks this event as finished."""
    explicit_payload = raw_event.get("media_end_payload", raw_event.get("media_end_id"))

    if explicit_payload is not None:
        return str(explicit_payload)

    for payload, _delay in _payloads_from_config(raw_event.get("payload")):
        decoded = payload.decode("utf-8") if payload is not None else ""
        media_id = _media_id_from_command(decoded)

        if media_id:
            return media_id

    return raw_event["id"]


def _media_id_from_command(payload: str) -> str | None:
    """Extract the id from `start;id;path_to_file` media commands."""
    parts = payload.split(";", 2)

    if len(parts) != 3 or parts[0] != "start" or not parts[1]:
        return None

    return parts[1]


def _media_stop_messages_from_config(raw_event: dict[str, Any]) -> tuple[EventMessage, ...]:
    """Build stop commands for every media item started by an event."""
    return tuple(
        EventMessage(topic=message.topic, payload=_encode_payload(stop_command))
        for message in _topic_messages_from_config(raw_event)
        for stop_command in (_media_stop_command(message.payload),)
        if stop_command is not None
    )


def _media_stop_command(payload: bytes | None) -> str | None:
    """Return `stop;id;path_to_file` for a configured media start command."""
    if payload is None:
        return None

    command = payload.decode("utf-8")
    parts = command.split(";", 2)

    if len(parts) != 3 or parts[0] != "start" or not parts[1]:
        return None

    return f"stop;{parts[1]};{parts[2]}"


def _media_end_event_id(raw_event: dict[str, Any]) -> str:
    """Return the generated media-end event id."""
    return f"{raw_event['id']}_off"


def _messages_from_config(raw_event: dict[str, Any], macros: dict[str, Any]) -> tuple[EventMessage, ...]:
    """Build outbound MQTT messages from topic/payload config.

    If topic and payload list lengths match, each payload is sent to the
    corresponding topic. Otherwise all payloads are sent to the first topic.
    """
    messages = _topic_messages_from_config(raw_event)
    macro_messages = _macro_messages_from_config(raw_event.get("macro"), macros)
    return messages + macro_messages


def _topic_messages_from_config(raw_event: dict[str, Any]) -> tuple[EventMessage, ...]:
    """Build outbound MQTT messages from explicit topic/payload config."""
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


def _macro_messages_from_config(raw_macro: Any, macros: dict[str, Any]) -> tuple[EventMessage, ...]:
    """Build MQTT messages from a configured macro."""
    if raw_macro is None:
        return ()

    if not isinstance(raw_macro, dict):
        raise ValueError("Event macro must be a JSON object.")

    messages: list[EventMessage] = []

    for macro_name, macro_value in raw_macro.items():
        messages.extend(_messages_for_macro(macro_name, macro_value, macros))

    return tuple(messages)


def _messages_for_macro(macro_name: Any, macro_value: Any, macros: dict[str, Any]) -> tuple[EventMessage, ...]:
    """Build MQTT messages for one short-form macro entry."""
    if not isinstance(macro_name, str):
        raise ValueError("Event macro names must be strings.")

    macro_definitions = macros.get("macros", macros)
    macro = macro_definitions.get(macro_name) if isinstance(macro_definitions, dict) else None

    if not isinstance(macro, dict):
        raise ValueError(f"Unknown event macro '{macro_name}'.")

    topics = _topics_for_macro(macro_name, macro, macros)
    value, delay = _macro_value_from_config(macro_name, macro_value)

    if _is_palette_macro(macro):
        return _palette_macro_messages(macro_name, delay, macro, topics)

    if _is_all_light_macro(macro):
        return _all_light_macro_messages(macro_name, value, delay, topics)

    return _focus_light_macro_messages(macro_name, value, delay, macro, topics, macros)


def _macro_value_from_config(macro_name: str, raw_value: Any) -> tuple[Any, float]:
    """Return the macro value and optional delay from config."""
    if isinstance(raw_value, list) and len(raw_value) == 2 and isinstance(raw_value[1], int | float):
        return raw_value[0], float(raw_value[1])

    if isinstance(raw_value, dict) and "value" in raw_value:
        delay = raw_value.get("delay", 0.0)

        if not isinstance(delay, int | float):
            raise ValueError(f"Event macro '{macro_name}' delay must be a number.")

        return raw_value["value"], float(delay)

    return raw_value, 0.0


def _is_all_light_macro(macro: dict[str, Any]) -> bool:
    """Return whether this macro sets every topic to the same value."""
    return "dimmed" not in macro and "max" not in macro and "values" not in macro


def _is_palette_macro(macro: dict[str, Any]) -> bool:
    """Return whether this macro sets configured topics to per-light values."""
    return "values" in macro


def _topics_for_macro(macro_name: str, macro: dict[str, Any], macros: dict[str, Any]) -> dict[str, str]:
    """Return the resolved topic map for a macro."""
    topic_group = macro.get("topic_group")

    if isinstance(topic_group, str):
        light_groups = macros.get("lights")

        if not isinstance(light_groups, dict):
            raise ValueError(f"Event macro '{macro_name}' references topic group '{topic_group}', but no lights groups are configured.")

        topics = light_groups.get(topic_group)
    else:
        topics = macro.get("topics", macro.get("lights"))

    if not isinstance(topics, dict) or not all(isinstance(topic, str) for topic in topics.values()):
        raise ValueError(f"Event macro '{macro_name}' must resolve to an object of id/topic pairs.")

    return topics


def _topics_for_light_group(macro_name: str, group_name: Any, macros: dict[str, Any]) -> dict[str, str]:
    """Return topics from a named light group in the shared macros config."""
    light_groups = macros.get("lights")

    if not isinstance(group_name, str):
        raise ValueError(f"Event macro '{macro_name}' light group name must be a string.")

    if not isinstance(light_groups, dict):
        raise ValueError(f"Event macro '{macro_name}' references light group '{group_name}', but no lights groups are configured.")

    topics = light_groups.get(group_name)

    if not isinstance(topics, dict) or not all(isinstance(topic, str) for topic in topics.values()):
        raise ValueError(f"Event macro '{macro_name}' light group '{group_name}' must resolve to an object of id/topic pairs.")

    return topics


def _focus_light_macro_messages(
    macro_name: str,
    bright_light: Any,
    delay: float,
    macro: dict[str, Any],
    lights: dict[str, str],
    macros: dict[str, Any],
) -> tuple[EventMessage, ...]:
    """Build MQTT messages for the focus-light macro."""
    if not isinstance(bright_light, str):
        raise ValueError(f"Event macro '{macro_name}' value must be a string light id.")

    if bright_light not in lights:
        raise ValueError(f"Bright light '{bright_light}' is not configured in macro '{macro_name}'.")

    max_value = macro.get("max")
    dimmed_value = macro.get("dimmed")

    brightness_messages = tuple(
        EventMessage(
            topic=topic,
            payload=_encode_payload(max_value if light_id == bright_light else dimmed_value),
            delay=delay,
        )
        for light_id, topic in lights.items()
    )

    return brightness_messages + _focus_light_color_messages(macro_name, delay, macro, macros)


def _focus_light_color_messages(
    macro_name: str,
    delay: float,
    macro: dict[str, Any],
    macros: dict[str, Any],
) -> tuple[EventMessage, ...]:
    """Build optional color messages for the focus-light macro."""
    color_group = macro.get("color_topic_group")
    colors = macro.get("colors")

    if color_group is None and colors is None:
        return ()

    if not isinstance(colors, dict):
        raise ValueError(f"Event macro '{macro_name}' colors must be an object of light id/color pairs.")

    color_topics = _topics_for_light_group(macro_name, color_group, macros)

    missing_lights = set(colors) - set(color_topics)

    if missing_lights:
        missing = ", ".join(sorted(str(light_id) for light_id in missing_lights))
        raise ValueError(f"Event macro '{macro_name}' colors reference unknown light ids: {missing}.")

    return tuple(
        EventMessage(topic=color_topics[light_id], payload=_encode_payload(color), delay=delay)
        for light_id, color in colors.items()
    )


def _all_light_macro_messages(macro_name: str, value: Any, delay: float, topics: dict[str, str]) -> tuple[EventMessage, ...]:
    """Build MQTT messages that set every configured light topic to one value."""
    return tuple(
        EventMessage(topic=topic, payload=_encode_payload(value), delay=delay)
        for topic in topics.values()
    )


def _palette_macro_messages(macro_name: str, delay: float, macro: dict[str, Any], topics: dict[str, str]) -> tuple[EventMessage, ...]:
    """Build MQTT messages that set configured topics to per-light values."""
    values = macro.get("values")

    if not isinstance(values, dict):
        raise ValueError(f"Event macro '{macro_name}' values must be an object of id/value pairs.")

    missing_topics = set(values) - set(topics)

    if missing_topics:
        missing = ", ".join(sorted(str(topic_id) for topic_id in missing_topics))
        raise ValueError(f"Event macro '{macro_name}' values reference unknown ids: {missing}.")

    return tuple(
        EventMessage(topic=topics[topic_id], payload=_encode_payload(value), delay=delay)
        for topic_id, value in values.items()
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

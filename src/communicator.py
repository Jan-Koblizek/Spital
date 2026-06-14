"""Communication with the outside world."""
from datetime import datetime
from dataclasses import dataclass
from threading import Lock
from threading import Timer
from typing import Callable
import paho.mqtt.client as mqtt
from config import mqtt_config

from interfaces import Event, EventMessage


# Function that receives decoded incoming MQTT messages.
MessageHandler = Callable[[str, str | None], None]


@dataclass(frozen=True)
class SentMessage:
    """One message sent through the communicator."""
    topic: str
    payload: str | None
    sent_at: str
    offline: bool

    def to_dict(self) -> dict[str, str | bool | None]:
        """Return a frontend-safe representation of this sent message."""
        return {
            "topic": self.topic,
            "payload": self.payload,
            "sent_at": self.sent_at,
            "offline": self.offline,
        }


class Communicator:
    """MQTT adapter used by the rest of the app.

    If the broker is unavailable, outbound messages are looped back into the
    message handler so the frontend can still drive the runtime without devices.
    """
    
    def __init__(self, message_handler: MessageHandler):
        """Initialize the communicator.

        Args:
            message_handler (MessageHandler): Function that handles incoming messages.
        """
        self.message_handler = message_handler
        self.mqtt_client: mqtt.Client | None = None
        self.mqtt_connected = False
        self._sent_messages: list[SentMessage] = []
        self._sent_messages_lock = Lock()
    
    def start(self):
        """Start handling MQTT traffic in the background."""
        try:
            self.mqtt_client = self._mqtt_init()
        except Exception as exc:
            self.mqtt_client = None
            self.mqtt_connected = False
            print(
                "Could not connect to MQTT broker "
                f"at {mqtt_config.host}:{mqtt_config.port}; continuing without MQTT. "
                f"{exc}"
            )
            return

        self.mqtt_client.loop_start()

    def stop(self):
        """Stop handling MQTT traffic."""
        if self.mqtt_client is None:
            return

        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.mqtt_client = None
        self.mqtt_connected = False
        
    def _mqtt_init(self):
        """Create and connect an MQTT client with all callbacks registered."""
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.username_pw_set(mqtt_config.username, mqtt_config.password)

        mqtt_client.on_connect = self.mqtt_on_connect
        mqtt_client.on_disconnect = self.mqtt_on_disconnect
        mqtt_client.on_message = self.mqtt_on_message

        mqtt_client.connect(mqtt_config.host, mqtt_config.port, keepalive=60)
        
        return mqtt_client

        
    def mqtt_on_connect(self, client, userdata, flags, reason_code, properties=None):
        """When we connect to the MQTT broker, we subscribe to relevant topics.

        Args:
            client: the MQTT client
            userdata:
            flags:
            reason_code: if not 0 code of the error
            properties:
        """
        if reason_code != 0:
            self.mqtt_connected = False
            print(f"Failed to connect to MQTT broker. Code: {reason_code}")
            return

        self.mqtt_connected = True
        print("Connected to MQTT broker.")
        # TODO subscribe only to the topics relevant to the inbound events.
        client.subscribe("#")   # subscribe to all the topics

    def mqtt_on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        """Track MQTT disconnects so frontend control can continue offline."""
        self.mqtt_connected = False
        print(f"Disconnected from MQTT broker. Code: {reason_code}")

    def mqtt_on_message(self, client, userdata, message):
        """Handle incoming MQTT message.
        
        Payload bytes are decoded to UTF-8 text before being handed to the
        application message handler.

        Args:
            client: MQTT client that received the message.
            userdata: optional MQTT user data.
            message: MQTT message to be handled elsewhere
        """
        self.message_handler(
            topic=message.topic,
            payload=self._decode_payload(message.payload),
        )

    def send_event(self, event: Event) -> None:
        """Send an event to connected devices."""
        for message in event.outbound_messages():
            self._send_event_message(message)

    def _send_event_message(self, message: EventMessage) -> None:
        """Publish one event message, optionally after a configured delay."""
        if message.delay <= 0:
            self.send_message(message.topic, message.payload)
            return

        Timer(
            message.delay,
            lambda: self.send_message(message.topic, message.payload),
        ).start()

    def send_message(self, topic: str, payload: bytes | None):
        """Send a message to MQTT, or loop it back locally while offline.

        Args:
            topic (str): topic to which we are sending the message
            payload (bytes | None): message we are sending

        Offline loopback is deliberate: it lets frontend-triggered events keep
        advancing the runtime when no broker is reachable.
        """
        print(f"sending: {topic}, {payload}")
        offline = self.mqtt_client is None or not self.mqtt_connected
        decoded_payload = self._decode_payload(payload)
        self._record_sent_message(topic, decoded_payload, offline)

        if offline:
            self.message_handler(topic, decoded_payload)
            return

        result = self.mqtt_client.publish(
            topic=topic,
            payload=payload,
            qos=1,  # Send at least once
            retain=False,
        )

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Failed to publish MQTT message. rc={result.rc}")

    def sent_messages(self) -> list[dict[str, str | bool | None]]:
        """Return recently sent MQTT messages for frontend display."""
        with self._sent_messages_lock:
            return [
                message.to_dict()
                for message in self._sent_messages
            ]

    def _record_sent_message(self, topic: str, payload: str | None, offline: bool) -> None:
        """Remember one outgoing message for the frontend log."""
        message = SentMessage(
            topic=topic,
            payload=payload,
            sent_at=datetime.now().isoformat(timespec="seconds"),
            offline=offline,
        )

        with self._sent_messages_lock:
            self._sent_messages.append(message)
            self._sent_messages = self._sent_messages[-5:]

    def _decode_payload(self, payload: bytes | None) -> str | None:
        """Decode MQTT payload bytes to text used by runtime logic."""
        if payload is None:
            return None

        return payload.decode("utf-8")

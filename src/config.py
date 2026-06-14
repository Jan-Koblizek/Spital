"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class MqttConfig:
    """Configuration for the MQTT broker."""
    host: str
    port: int
    username: str | None
    password: str | None


@dataclass(frozen=True)
class EventConfig:
    """Configuration for event definition files."""
    directory: Path


@dataclass(frozen=True)
class DeviceStateConfig:
    """Configuration for device state definition files."""
    directory: Path
    request_topic: str
    request_payload: bytes | None


@dataclass(frozen=True)
class FrontendConfig:
    """Configuration for the frontend HTTP server."""
    host: str
    port: int


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _path_from_env(name: str, default: Path) -> Path:
    """Return an absolute path from an env var or a project-relative default."""
    raw_path = os.getenv(name)

    if not raw_path:
        return default

    path = Path(raw_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


mqtt_config = MqttConfig(
    host=os.getenv("MQTT_HOST", "localhost"),
    port=int(os.getenv("MQTT_PORT", "1883")),
    username=os.getenv("MQTT_USERNAME") or None,
    password=os.getenv("MQTT_PASSWORD") or None,
)

event_config = EventConfig(
    directory=_path_from_env("EVENT_CONFIG_DIR", PROJECT_ROOT / "event_configs"),
)

device_state_config = DeviceStateConfig(
    directory=_path_from_env("DEVICE_STATE_CONFIG_DIR", PROJECT_ROOT / "device_state_configs"),
    request_topic=os.getenv("DEVICE_STATE_REQUEST_TOPIC", "spital/state/request"),
    request_payload=(
        os.getenv("DEVICE_STATE_REQUEST_PAYLOAD", "1").encode("utf-8")
        if os.getenv("DEVICE_STATE_REQUEST_PAYLOAD", "1") != ""
        else None
    ),
)

frontend_config = FrontendConfig(
    host=os.getenv("FRONTEND_HOST", "127.0.0.1"),
    port=int(os.getenv("FRONTEND_PORT", "8000")),
)

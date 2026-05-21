"""
Device Setup Models

Data models for the device setup/configuration process.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class SetupStatus(str, Enum):
    """Status of device setup process."""

    UNCONFIGURED = "unconfigured"  # Device discovered but not configured
    PENDING = "pending"  # Setup in progress
    CONFIGURED = "configured"  # Successfully configured
    FAILED = "failed"  # Setup failed
    OUTDATED = "outdated"  # Device points to different/old OCT instance
    OFFLINE = "offline"  # Device not reachable (last_seen > threshold)
    UNKNOWN = "unknown"  # Initial state, not yet checked
    RESTORED = "restored"  # Device restored to factory-like state via Restore Wizard


class SetupStep(str, Enum):
    """Individual steps in the setup process."""

    USB_INSERT = "usb_insert"  # User inserts USB with remote_services
    DEVICE_REBOOT = "device_reboot"  # Device needs reboot after USB
    SSH_CONNECT = "ssh_connect"  # Connect via SSH
    SSH_PERSIST = "ssh_persist"  # Make SSH persistent
    CONFIG_BACKUP = "config_backup"  # Backup original config
    CONFIG_MODIFY = "config_modify"  # Modify BMX URL
    VERIFY = "verify"  # Verify configuration
    COMPLETE = "complete"  # Setup complete


@dataclass
class SetupProgress:
    """Progress of an ongoing setup process."""

    device_id: str
    current_step: SetupStep
    status: SetupStatus
    message: str = ""
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "device_id": self.device_id,
            "current_step": self.current_step.value,
            "status": self.status.value,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class ModelInstructions:
    """Model-specific setup instructions and purchase recommendations."""

    model_name: str
    display_name: str
    usb_port_type: str  # Primary USB type (backward compat)
    usb_port_location: str
    adapter_needed: bool
    adapter_recommendation: str
    usb_port_types: List[str] = field(default_factory=list)
    image_url: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.usb_port_types:
            self.usb_port_types = [self.usb_port_type]

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "model_name": self.model_name,
            "display_name": self.display_name,
            "usb_port_type": self.usb_port_type,
            "usb_port_types": self.usb_port_types,
            "usb_port_location": self.usb_port_location,
            "adapter_needed": self.adapter_needed,
            "adapter_recommendation": self.adapter_recommendation,
            "image_url": self.image_url,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Model-specific instructions database
#
# USB types sourced from devices/hardware.py (SSOT).
# ST20/ST30 sm2 span Gen II (Micro-USB) and Gen III (USB-A) —
# both types listed since generation is not detectable via API.
# ---------------------------------------------------------------------------
_USB_A_DIRECT = "Standard USB-Stick direkt einstecken"
_REAR_SERVICE = "Rückseite, beschriftet 'SERVICE'"
MODEL_INSTRUCTIONS: dict[str, ModelInstructions] = {
    "SoundTouch 10": ModelInstructions(
        model_name="SoundTouch 10",
        display_name="Bose SoundTouch 10",
        usb_port_type="micro-usb",
        usb_port_location="Rückseite, neben AUX-Eingang, beschriftet 'SETUP'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) oder USB-C auf Micro-USB (~5€)",
        notes=[
            "Setup-Port ist der Micro-USB Anschluss",
            "Gerät muss nach USB-Stick Einstecken neu gestartet werden",
        ],
    ),
    "SoundTouch 20": ModelInstructions(
        model_name="SoundTouch 20",
        display_name="Bose SoundTouch 20",
        usb_port_type="micro-usb",
        usb_port_types=["micro-usb", "usb-a"],
        usb_port_location="Rückseite, beschriftet 'SETUP'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) — nur bei Micro-USB-Modellen nötig",
        notes=[
            "Series II hat Micro-USB, Series III hat USB-A",
            "Port befindet sich auf der Rückseite, beschriftet 'SETUP'",
        ],
    ),
    "SoundTouch 30": ModelInstructions(
        model_name="SoundTouch 30",
        display_name="Bose SoundTouch 30",
        usb_port_type="micro-usb",
        usb_port_types=["micro-usb", "usb-a"],
        usb_port_location="Rückseite, neben Ethernet-Port, beschriftet 'SETUP'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) — nur bei Micro-USB-Modellen nötig",
        notes=[
            "Series II hat Micro-USB, Series III hat USB-A",
            "Ethernet-Verbindung empfohlen für stabilen SSH-Zugang",
        ],
    ),
    "SoundTouch 300": ModelInstructions(
        model_name="SoundTouch 300",
        display_name="Bose SoundTouch 300 Soundbar",
        usb_port_type="usb-a",
        usb_port_location=_REAR_SERVICE,
        adapter_needed=False,
        adapter_recommendation=_USB_A_DIRECT,
        notes=[
            "USB-A Port auf der Rückseite",
        ],
    ),
    "SoundTouch Portable": ModelInstructions(
        model_name="SoundTouch Portable",
        display_name="Bose SoundTouch Portable",
        usb_port_type="micro-usb",
        usb_port_location="Unterseite, hinter Gummiklappe",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€)",
        notes=[
            "Akku muss geladen sein oder Netzteil angeschlossen",
        ],
    ),
    "SoundTouch SA-4": ModelInstructions(
        model_name="SoundTouch SA-4",
        display_name="Bose SoundTouch SA-4 Amplifier",
        usb_port_type="usb-a",
        usb_port_location=_REAR_SERVICE,
        adapter_needed=False,
        adapter_recommendation=_USB_A_DIRECT,
        notes=[
            "Verstärker sollte mit Lautsprecher verbunden sein für Audio-Feedback",
        ],
    ),
    "SoundTouch SA-5": ModelInstructions(
        model_name="SoundTouch SA-5",
        display_name="Bose SoundTouch SA-5 Amplifier",
        usb_port_type="usb-a",
        usb_port_location=_REAR_SERVICE,
        adapter_needed=False,
        adapter_recommendation=_USB_A_DIRECT,
        notes=[
            "Verstärker sollte mit Lautsprecher verbunden sein",
        ],
    ),
    "Wave SoundTouch": ModelInstructions(
        model_name="Wave SoundTouch",
        display_name="Bose Wave SoundTouch Music System",
        usb_port_type="usb-a",
        usb_port_types=["usb-a", "micro-usb"],
        usb_port_location="Rückseite des Pedestal-Adapters",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter — nur bei Micro-USB-Pedestal nötig",
        notes=[
            "Setup-Port ist am SoundTouch Pedestal, nicht am Wave Radio selbst",
            "Pedestal hat je nach Baujahr USB-A oder Micro-USB",
        ],
    ),
    "SoundTouch Cinemate": ModelInstructions(
        model_name="SoundTouch Cinemate",
        display_name="Bose SoundTouch Cinemate",
        usb_port_type="usb-a",
        usb_port_location="Rückseite der Steuereinheit",
        adapter_needed=False,
        adapter_recommendation=_USB_A_DIRECT,
        notes=[],
    ),
    "SoundTouch Wireless Link": ModelInstructions(
        model_name="SoundTouch Wireless Link",
        display_name="Bose SoundTouch Wireless Link Adapter",
        usb_port_type="usb-a",
        usb_port_location="Rückseite",
        adapter_needed=False,
        adapter_recommendation=_USB_A_DIRECT,
        notes=[],
    ),
    "Lifestyle": ModelInstructions(
        model_name="Lifestyle",
        display_name="Bose Lifestyle SoundTouch",
        usb_port_type="usb-a",
        usb_port_location="Rückseite der Steuereinheit",
        adapter_needed=False,
        adapter_recommendation=_USB_A_DIRECT,
        notes=[
            "Einige Lifestyle-Modelle (bardeen) haben keinen USB-Port",
        ],
    ),
}

# Default instructions for unknown models
DEFAULT_INSTRUCTIONS = ModelInstructions(
    model_name="Unknown",
    display_name="Bose SoundTouch Gerät",
    usb_port_type="micro-usb",
    usb_port_types=["micro-usb", "usb-a"],
    usb_port_location="Rückseite, meist beschriftet 'SETUP' oder 'SERVICE'",
    adapter_needed=True,
    adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) — nur bei Micro-USB nötig",
    notes=[
        "Prüfe ob dein Gerät einen Micro-USB oder USB-A Port hat",
        "Micro-USB: OTG-Adapter benötigt. USB-A: Stick direkt einstecken",
    ],
)


def get_model_instructions(model_name: str) -> ModelInstructions:
    """Get setup instructions for a specific model."""
    # Try exact match first
    if model_name in MODEL_INSTRUCTIONS:
        return MODEL_INSTRUCTIONS[model_name]

    # Try partial match
    for key, instructions in MODEL_INSTRUCTIONS.items():
        if key.lower() in model_name.lower() or model_name.lower() in key.lower():
            return instructions

    # Return default
    return DEFAULT_INSTRUCTIONS

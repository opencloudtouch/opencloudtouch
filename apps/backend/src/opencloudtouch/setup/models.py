"""
Device Setup Models

Data models for the device setup/configuration process.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class SetupStatus(str, Enum):
    """Status of device setup process."""
    
    UNCONFIGURED = "unconfigured"  # Device discovered but not configured
    PENDING = "pending"            # Setup in progress
    CONFIGURED = "configured"      # Successfully configured
    FAILED = "failed"              # Setup failed


class SetupStep(str, Enum):
    """Individual steps in the setup process."""
    
    USB_INSERT = "usb_insert"           # User inserts USB with remote_services
    DEVICE_REBOOT = "device_reboot"     # Device needs reboot after USB
    SSH_CONNECT = "ssh_connect"         # Connect via SSH
    SSH_PERSIST = "ssh_persist"         # Make SSH persistent
    CONFIG_BACKUP = "config_backup"     # Backup original config
    CONFIG_MODIFY = "config_modify"     # Modify BMX URL
    VERIFY = "verify"                   # Verify configuration
    COMPLETE = "complete"               # Setup complete


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
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class ModelInstructions:
    """Model-specific setup instructions and purchase recommendations."""
    
    model_name: str
    display_name: str
    usb_port_type: str  # "micro-usb" | "usb-a" | "usb-c"
    usb_port_location: str
    adapter_needed: bool
    adapter_recommendation: str
    image_url: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "model_name": self.model_name,
            "display_name": self.display_name,
            "usb_port_type": self.usb_port_type,
            "usb_port_location": self.usb_port_location,
            "adapter_needed": self.adapter_needed,
            "adapter_recommendation": self.adapter_recommendation,
            "image_url": self.image_url,
            "notes": self.notes,
        }


# Model-specific instructions database
MODEL_INSTRUCTIONS: dict[str, ModelInstructions] = {
    "SoundTouch 10": ModelInstructions(
        model_name="SoundTouch 10",
        display_name="Bose SoundTouch 10",
        usb_port_type="micro-usb",
        usb_port_location="Rückseite, neben AUX-Eingang, beschriftet 'SETUP'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) oder USB-C auf Micro-USB (~5€)",
        notes=[
            "Setup-Port ist der Micro-USB Anschluss, NICHT der USB-A Port",
            "Gerät muss nach USB-Stick Einstecken neu gestartet werden",
        ],
    ),
    "SoundTouch 20": ModelInstructions(
        model_name="SoundTouch 20",
        display_name="Bose SoundTouch 20",
        usb_port_type="micro-usb",
        usb_port_location="Rückseite, unter dem AUX-Eingang, beschriftet 'SETUP'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) oder USB-C auf Micro-USB (~5€)",
        notes=[
            "Der normale USB-A Port an der Seite funktioniert NICHT für Setup",
            "Nutze den Micro-USB 'Setup' Port hinten",
        ],
    ),
    "SoundTouch 30": ModelInstructions(
        model_name="SoundTouch 30",
        display_name="Bose SoundTouch 30",
        usb_port_type="micro-usb",
        usb_port_location="Rückseite, neben Ethernet-Port, beschriftet 'SETUP'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) oder USB-C auf Micro-USB (~5€)",
        notes=[
            "Ethernet-Verbindung empfohlen für stabilen SSH-Zugang",
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
        usb_port_type="micro-usb",
        usb_port_location="Rückseite, beschriftet 'Setup'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€)",
        notes=[
            "Verstärker sollte mit Lautsprecher verbunden sein für Audio-Feedback",
        ],
    ),
    "SoundTouch SA-5": ModelInstructions(
        model_name="SoundTouch SA-5",
        display_name="Bose SoundTouch SA-5 Amplifier",
        usb_port_type="micro-usb",
        usb_port_location="Rückseite, beschriftet 'Setup'",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€)",
        notes=[
            "Verstärker sollte mit Lautsprecher verbunden sein",
        ],
    ),
    "Wave SoundTouch": ModelInstructions(
        model_name="Wave SoundTouch",
        display_name="Bose Wave SoundTouch Music System",
        usb_port_type="micro-usb",
        usb_port_location="Rückseite des Pedestal-Adapters",
        adapter_needed=True,
        adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€)",
        notes=[
            "Setup-Port ist am SoundTouch Pedestal, nicht am Wave Radio selbst",
        ],
    ),
}

# Default instructions for unknown models
DEFAULT_INSTRUCTIONS = ModelInstructions(
    model_name="Unknown",
    display_name="Bose SoundTouch Gerät",
    usb_port_type="micro-usb",
    usb_port_location="Rückseite, meist beschriftet 'SETUP'",
    adapter_needed=True,
    adapter_recommendation="USB-A auf Micro-USB OTG Adapter (~3€) oder USB-C auf Micro-USB (~5€)",
    notes=[
        "Suche nach einem Micro-USB Port mit der Beschriftung 'Setup' oder 'Service'",
        "Der normale USB-A Port (falls vorhanden) funktioniert meist NICHT",
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

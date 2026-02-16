"""Unit tests for setup models.

Tests for SetupStatus, SetupStep, SetupProgress, and ModelInstructions.
Following TDD Red-Green-Refactor cycle.
"""

import pytest
from datetime import datetime

from opencloudtouch.setup.models import (
    SetupStatus,
    SetupStep,
    SetupProgress,
    ModelInstructions,
    MODEL_INSTRUCTIONS,
    get_model_instructions,
    DEFAULT_INSTRUCTIONS,
)


class TestSetupStatus:
    """Tests for SetupStatus enum."""

    def test_status_values(self):
        """Test all status values exist and are strings."""
        assert SetupStatus.UNCONFIGURED.value == "unconfigured"
        assert SetupStatus.PENDING.value == "pending"
        assert SetupStatus.CONFIGURED.value == "configured"
        assert SetupStatus.FAILED.value == "failed"

    def test_status_is_string_enum(self):
        """Test status can be used as string."""
        status = SetupStatus.CONFIGURED
        assert str(status) == "SetupStatus.CONFIGURED"
        assert status.value == "configured"


class TestSetupStep:
    """Tests for SetupStep enum."""

    def test_all_steps_exist(self):
        """Test all expected steps are defined."""
        expected_steps = [
            "usb_insert",
            "device_reboot",
            "ssh_connect",
            "ssh_persist",
            "config_backup",
            "config_modify",
            "verify",
            "complete",
        ]
        actual_steps = [step.value for step in SetupStep]
        assert set(expected_steps) == set(actual_steps)

    def test_step_order_makes_sense(self):
        """Test steps follow logical order."""
        steps = list(SetupStep)
        # USB insert should be before SSH connect
        assert steps.index(SetupStep.USB_INSERT) < steps.index(SetupStep.SSH_CONNECT)
        # SSH connect should be before config modify
        assert steps.index(SetupStep.SSH_CONNECT) < steps.index(SetupStep.CONFIG_MODIFY)
        # Verify should be before complete
        assert steps.index(SetupStep.VERIFY) < steps.index(SetupStep.COMPLETE)


class TestSetupProgress:
    """Tests for SetupProgress dataclass."""

    @pytest.fixture
    def sample_progress(self):
        """Create sample progress instance."""
        return SetupProgress(
            device_id="AABBCC112233",
            current_step=SetupStep.SSH_CONNECT,
            status=SetupStatus.PENDING,
            message="Connecting via SSH...",
        )

    def test_progress_creation(self, sample_progress):
        """Test basic progress creation."""
        assert sample_progress.device_id == "AABBCC112233"
        assert sample_progress.current_step == SetupStep.SSH_CONNECT
        assert sample_progress.status == SetupStatus.PENDING
        assert sample_progress.message == "Connecting via SSH..."
        assert sample_progress.error is None
        assert sample_progress.completed_at is None

    def test_progress_has_started_at(self, sample_progress):
        """Test progress has started_at timestamp."""
        assert isinstance(sample_progress.started_at, datetime)

    def test_progress_to_dict(self, sample_progress):
        """Test to_dict serialization."""
        result = sample_progress.to_dict()

        assert result["device_id"] == "AABBCC112233"
        assert result["current_step"] == "ssh_connect"
        assert result["status"] == "pending"
        assert result["message"] == "Connecting via SSH..."
        assert result["error"] is None
        assert "started_at" in result
        assert result["completed_at"] is None

    def test_progress_to_dict_with_error(self):
        """Test to_dict with error message."""
        progress = SetupProgress(
            device_id="TEST123",
            current_step=SetupStep.SSH_CONNECT,
            status=SetupStatus.FAILED,
            message="Connection failed",
            error="Connection refused",
        )
        result = progress.to_dict()

        assert result["status"] == "failed"
        assert result["error"] == "Connection refused"

    def test_progress_to_dict_with_completed_at(self):
        """Test to_dict with completed_at timestamp."""
        completed_time = datetime(2026, 2, 15, 12, 0, 0)
        progress = SetupProgress(
            device_id="TEST123",
            current_step=SetupStep.COMPLETE,
            status=SetupStatus.CONFIGURED,
            message="Setup complete",
            completed_at=completed_time,
        )
        result = progress.to_dict()

        assert result["completed_at"] == completed_time.isoformat()


class TestModelInstructions:
    """Tests for ModelInstructions dataclass."""

    @pytest.fixture
    def sample_instructions(self):
        """Create sample instructions."""
        return ModelInstructions(
            model_name="SoundTouch 10",
            display_name="Bose SoundTouch 10",
            usb_port_type="micro-usb",
            usb_port_location="Back panel, labeled 'SETUP'",
            adapter_needed=True,
            adapter_recommendation="USB-A to Micro-USB OTG adapter",
            notes=["Note 1", "Note 2"],
        )

    def test_instructions_creation(self, sample_instructions):
        """Test basic instructions creation."""
        assert sample_instructions.model_name == "SoundTouch 10"
        assert sample_instructions.display_name == "Bose SoundTouch 10"
        assert sample_instructions.usb_port_type == "micro-usb"
        assert sample_instructions.adapter_needed is True
        assert len(sample_instructions.notes) == 2

    def test_instructions_to_dict(self, sample_instructions):
        """Test to_dict serialization."""
        result = sample_instructions.to_dict()

        assert result["model_name"] == "SoundTouch 10"
        assert result["display_name"] == "Bose SoundTouch 10"
        assert result["usb_port_type"] == "micro-usb"
        assert result["usb_port_location"] == "Back panel, labeled 'SETUP'"
        assert result["adapter_needed"] is True
        assert result["adapter_recommendation"] == "USB-A to Micro-USB OTG adapter"
        assert result["image_url"] is None
        assert result["notes"] == ["Note 1", "Note 2"]

    def test_instructions_default_values(self):
        """Test default values for optional fields."""
        instructions = ModelInstructions(
            model_name="Test",
            display_name="Test Model",
            usb_port_type="usb-a",
            usb_port_location="Back",
            adapter_needed=False,
            adapter_recommendation="None needed",
        )
        assert instructions.image_url is None
        assert instructions.notes == []


class TestModelInstructionsDatabase:
    """Tests for MODEL_INSTRUCTIONS database."""

    def test_known_models_exist(self):
        """Test known SoundTouch models have instructions."""
        expected_models = [
            "SoundTouch 10",
            "SoundTouch 20",
            "SoundTouch 30",
            "SoundTouch Portable",
            "SoundTouch SA-4",
        ]
        for model in expected_models:
            assert model in MODEL_INSTRUCTIONS, f"Missing instructions for {model}"

    def test_all_instructions_have_required_fields(self):
        """Test all instructions have required fields."""
        for model_name, instructions in MODEL_INSTRUCTIONS.items():
            assert instructions.model_name == model_name
            assert instructions.display_name  # Non-empty
            assert instructions.usb_port_type in ["micro-usb", "usb-a", "usb-c"]
            assert instructions.usb_port_location  # Non-empty
            assert isinstance(instructions.adapter_needed, bool)
            assert instructions.adapter_recommendation  # Non-empty

    def test_all_models_need_adapter(self):
        """Test all known SoundTouch models need USB adapter."""
        # SoundTouch devices use micro-USB but USB sticks are USB-A
        for instructions in MODEL_INSTRUCTIONS.values():
            if instructions.usb_port_type == "micro-usb":
                assert instructions.adapter_needed is True


class TestGetModelInstructions:
    """Tests for get_model_instructions function."""

    def test_exact_match(self):
        """Test exact model name match."""
        instructions = get_model_instructions("SoundTouch 10")
        assert instructions.model_name == "SoundTouch 10"

    def test_partial_match(self):
        """Test partial model name match."""
        # Should match "SoundTouch 30" when passed a substring
        instructions = get_model_instructions("30")
        assert "30" in instructions.model_name

    def test_case_insensitive_partial_match(self):
        """Test case-insensitive matching."""
        instructions = get_model_instructions("soundtouch 10")
        assert instructions.model_name == "SoundTouch 10"

    def test_unknown_model_returns_default(self):
        """Test unknown model returns default instructions."""
        instructions = get_model_instructions("Unknown Device XYZ")
        assert instructions == DEFAULT_INSTRUCTIONS
        assert instructions.model_name == "Unknown"

    def test_default_instructions_are_sensible(self):
        """Test default instructions provide useful info."""
        assert DEFAULT_INSTRUCTIONS.adapter_needed is True
        assert "micro-usb" in DEFAULT_INSTRUCTIONS.usb_port_type.lower()
        assert len(DEFAULT_INSTRUCTIONS.notes) > 0

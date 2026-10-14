"""Composed WizardService facade.

Method bodies live in the per-step mixin files in this package; this class
only assembles them. See the setup/wizard/ row in docs/ARCHITECTURE.md's
module table.
"""

from opencloudtouch.setup.wizard.base import WizardServiceBase
from opencloudtouch.setup.wizard.ntp_patch import NtpPatchMixin
from opencloudtouch.setup.wizard.step3_connectivity import Step3ConnectivityMixin
from opencloudtouch.setup.wizard.step4_backup import Step4BackupMixin
from opencloudtouch.setup.wizard.step5_config import Step5ConfigMixin
from opencloudtouch.setup.wizard.step6_hosts import Step6HostsMixin
from opencloudtouch.setup.wizard.step8_finalize_verify import Step8FinalizeVerifyMixin
from opencloudtouch.setup.wizard.step9_completion import Step9CompletionMixin


class WizardService(
    Step3ConnectivityMixin,
    Step4BackupMixin,
    Step5ConfigMixin,
    Step6HostsMixin,
    NtpPatchMixin,
    Step8FinalizeVerifyMixin,
    Step9CompletionMixin,
    WizardServiceBase,
):
    """Orchestrates the device setup wizard steps — see per-step mixins for logic."""

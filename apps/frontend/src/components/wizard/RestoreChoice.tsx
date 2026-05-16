/**
 * RestoreChoice - Clean Restore or Restore from Backup
 */
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import WizardStep from "./WizardStep";

interface RestoreChoiceProps {
  stepNumber: number;
  onCleanRestore: () => void;
  onBackupRestore: () => void;
  onPrevious: () => void;
}

export default function RestoreChoice({
  stepNumber,
  onCleanRestore,
  onBackupRestore,
  onPrevious,
}: Readonly<RestoreChoiceProps>) {
  const { t } = useTranslation();

  return (
    <WizardStep
      stepNumber={stepNumber}
      title={t("restore.restore_choice.title", "Choose Restore Type")}
      description={t(
        "restore.restore_choice.description",
        "Select how you want to restore the device."
      )}
      onPrevious={onPrevious}
    >
      <div className="wizard-choice__cards">
        <motion.button
          className="wizard-choice__card"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onCleanRestore}
        >
          <span className="wizard-choice__icon">🧹</span>
          <h3>{t("restore.restore_choice.clean_title", "Clean Restore")}</h3>
          <p>
            {t(
              "restore.restore_choice.clean_desc",
              "Remove all OCT modifications. No backup needed."
            )}
          </p>
        </motion.button>

        <motion.button
          className="wizard-choice__card"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onBackupRestore}
        >
          <span className="wizard-choice__icon">📦</span>
          <h3>{t("restore.restore_choice.backup_title", "Restore from Backup")}</h3>
          <p>
            {t(
              "restore.restore_choice.backup_desc",
              "Restore original config files from USB backup."
            )}
          </p>
        </motion.button>
      </div>
    </WizardStep>
  );
}

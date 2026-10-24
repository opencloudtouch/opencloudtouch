/** WizardChoice: logic unchanged, markup restyled. File: components/wizard/WizardChoice.tsx */
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Icon } from "./Icon";
import "./wizard-base.css"; // replaces WizardChoice.css

interface WizardChoiceProps {
  readonly onSelectSetup: () => void;
  readonly onSelectRestore: () => void;
}

export default function WizardChoice({ onSelectSetup, onSelectRestore }: WizardChoiceProps) {
  const { t } = useTranslation();

  return (
    <div className="wizard-choice">
      <h2 className="wizard-choice__title">
        {t("restore.choice.title", "What would you like to do?")}
      </h2>
      <div className="wizard-choice__cards">
        <motion.button
          className="wizard-choice__card wizard-choice__card--setup"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onSelectSetup}
        >
          <span className="wizard-choice__icon">{Icon.Settings()}</span>
          <h3>{t("restore.choice.setup_title", "Setup Wizard")}</h3>
          <p>{t("restore.choice.setup_desc", "Configure device for OpenCloudTouch")}</p>
        </motion.button>

        <motion.button
          className="wizard-choice__card wizard-choice__card--restore"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onSelectRestore}
        >
          <span className="wizard-choice__icon">{Icon.Rotate(26)}</span>
          <h3>{t("restore.choice.restore_title", "Restore Wizard")}</h3>
          <p>
            {t("restore.choice.restore_desc", "Undo all OCT changes and restore factory state")}
          </p>
        </motion.button>
      </div>
    </div>
  );
}

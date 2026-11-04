import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./DeviceOfflineBanner.css";

interface DeviceOfflineBannerProps {
  deviceName?: string;
}

export default function DeviceOfflineBanner({ deviceName }: Readonly<DeviceOfflineBannerProps>) {
  const { t } = useTranslation();
  return (
    <div
      className="wz-status wz-status--warning dob"
      role="alert"
      data-testid="device-offline-banner"
    >
      <span className="wz-icon" aria-hidden="true">
        {Icon.WifiOff(24)}
      </span>
      <div className="wz-status-body">
        <span className="wz-status-title">{t("errors.offlineTitle")}</span>
        <span className="wz-status-text">
          {deviceName
            ? t("errors.offlineDetail", { name: deviceName })
            : t("errors.offlineDetailNoName")}
        </span>
      </div>
    </div>
  );
}

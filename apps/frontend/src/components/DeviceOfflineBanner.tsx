import { useTranslation } from "react-i18next";
import "./DeviceOfflineBanner.css";

interface DeviceOfflineBannerProps {
  deviceName?: string;
}

export default function DeviceOfflineBanner({ deviceName }: Readonly<DeviceOfflineBannerProps>) {
  const { t } = useTranslation();
  return (
    <div className="device-offline-banner" role="alert" data-testid="device-offline-banner">
      <div className="offline-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
          <path d="M22.99 9C19.15 5.16 13.8 3.76 8.84 4.78l2.52 2.52c3.47-.17 6.99 1.05 9.63 3.7l2-2zM18.99 13c-1.29-1.29-2.84-2.13-4.49-2.56l3.53 3.53.96-.97zM2 3.05L5.07 6.1C3.6 6.82 2.22 7.78 1 9l2 2c1.02-1.02 2.17-1.82 3.41-2.4l2.52 2.52C7.45 11.69 6.12 12.61 5 14l2 2c1.05-1.31 2.43-2.18 3.95-2.6l2.16 2.16C12.08 15.85 11.06 16.34 10.16 17l1.83 2.26 1.43 1.77L17.98 26l1.27-1.27L3.27 1.78 2 3.05z" />
        </svg>
      </div>
      <div className="offline-text">
        <span className="offline-title">{t("errors.offlineTitle")}</span>
        <span className="offline-detail">
          {deviceName
            ? t("errors.offlineDetail", { name: deviceName })
            : t("errors.offlineDetailNoName")}
        </span>
      </div>
    </div>
  );
}

import { useTranslation } from "react-i18next";
import type { Device } from "../components/DeviceSwiper";
import DeviceNameEditor from "../components/DeviceNameEditor";
import RemoveDevice from "../components/RemoveDevice";
import { Icon } from "../components/Icon";
import { StereoPairBadge } from "../components/StereoPairCard";
import { renameStereoPair } from "../api/stereoPairs";

/** Name of the card: a stereo pair renames the pair, a single device renames itself. */
export function CardName({
  device,
  stereoPairId,
  pairName,
}: Readonly<{ device?: Device; stereoPairId: number | null; pairName: string }>) {
  const { t } = useTranslation();
  if (!device) {
    return (
      <h2 className="rp-device-name" data-test="device-name">
        {t("presets.unknownDevice")}
      </h2>
    );
  }
  if (stereoPairId === null) {
    return <DeviceNameEditor deviceId={device.device_id} name={device.name} />;
  }
  return (
    <DeviceNameEditor
      deviceId={device.device_id}
      name={pairName}
      maxLength={100}
      rename={async (name) => ({
        name: (await renameStereoPair(stereoPairId, name)).name,
      })}
    />
  );
}

/** Zone badge of the card and, for a zone member, the hint that names the master. */
export function ZoneRow({
  role,
  isZoneMember,
  masterName,
}: Readonly<{
  role: string;
  isZoneMember: boolean;
  masterName: string;
}>) {
  const { t } = useTranslation();
  return (
    <div className="dv-zone-row">
      <span className="lc-zone" data-test="device-zone">
        {Icon.Link(16)}
        <span>{role === "master" ? t("multiroom.masterBadge") : t("multiroom.slaveBadge")}</span>
      </span>
      {isZoneMember && (
        <p id="dv-slave-hint" className="dv-zone-hint">
          {t("device.slaveHint", { master: masterName })}
        </p>
      )}
    </div>
  );
}

/** Stereo footer of the card: pair badge and the names of both speakers. */
export function StereoRow({
  deviceName,
  partnerName,
}: Readonly<{ deviceName?: string; partnerName: string }>) {
  const { t } = useTranslation();
  return (
    <div className="dv-zone-row sp-devrow">
      <StereoPairBadge />
      {partnerName && (
        <span className="sp-partner" data-test="device-stereo-members">
          {t("stereo.pairMembers", "Links: {{left}} · Rechts: {{right}}", {
            left: deviceName,
            right: partnerName,
          })}
        </span>
      )}
    </div>
  );
}

/** Remove button of the card; for a stereo pair it dissolves the pair instead. */
export function CardRemove({
  device,
  offline,
  stereoPairId,
  pairName,
  partnerName,
  onRemoved,
  onDissolved,
}: Readonly<{
  device: Device;
  offline: boolean;
  stereoPairId: number | null;
  pairName: string;
  partnerName: string;
  onRemoved: (deviceId: string) => void;
  onDissolved: () => void;
}>) {
  const isPair = stereoPairId !== null;
  return (
    <RemoveDevice
      deviceId={device.device_id}
      ip={device.ip ?? ""}
      offline={offline}
      onRemoved={onRemoved}
      pair={
        isPair
          ? {
              id: stereoPairId,
              left: device.name ?? "",
              right: partnerName,
              // both speakers are single devices again: the list is fetched anew
              onDissolved,
            }
          : undefined
      }
      name={isPair ? pairName : (device.name ?? "")}
    />
  );
}

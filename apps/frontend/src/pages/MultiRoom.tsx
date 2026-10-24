import { useId, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Device } from "../components/DeviceSwiper";
import { useZoneBuilder } from "../hooks/useZoneBuilder";
import { useVolume } from "../hooks/useVolume";
import { useNowPlaying } from "../hooks/useNowPlaying";
import type { ZoneInfo } from "../api/zones";
import VolumeSlider from "../components/VolumeSlider";
import NowPlaying from "../components/NowPlaying";
import ConfirmDialog from "../components/ConfirmDialog";
import { DeviceNowPlaying } from "../components/DeviceNowPlaying";
import { Icon } from "../components/Icon";
import "./MultiRoom.css";

interface MultiRoomProps {
  readonly devices?: Device[];
}

// ---- Zone Volume per Member ----

function ZoneMemberVolume({ deviceId }: Readonly<{ deviceId: string }>) {
  const { volume, muted, setDeviceVolume, toggleMute } = useVolume(deviceId);
  return (
    <div className="zn-member-volume">
      <VolumeSlider
        volume={volume}
        onVolumeChange={setDeviceVolume}
        muted={muted}
        onMuteToggle={toggleMute}
      />
    </div>
  );
}

// ---- Zone Now Playing (compact) ----

function ZoneNowPlaying({ masterId }: Readonly<{ masterId: string }>) {
  const { t } = useTranslation();
  const { nowPlaying } = useNowPlaying(masterId);
  if (!nowPlaying || nowPlaying.source === "STANDBY") {
    return (
      <div className="zn-np zn-np--standby">
        <span aria-hidden="true">{Icon.Power(18)}</span>
        <span>{t("multiroom.standby")}</span>
      </div>
    );
  }
  return (
    <div className="zn-np">
      <NowPlaying
        nowPlaying={{
          art_url: nowPlaying.artwork_url ?? undefined,
          station: nowPlaying.station_name ?? undefined,
          track: nowPlaying.track ?? undefined,
          artist: nowPlaying.artist ?? undefined,
          play_status: nowPlaying.state,
          source: nowPlaying.source,
        }}
      />
    </div>
  );
}

// ---- Selectable device card ----
// The checkbox is a real <input> whose <label> is only the device name. The label is stretched over the card
// (::after), so the whole card toggles, while the "make master" button is a sibling outside the label.

interface DeviceCardProps {
  device: Device;
  index: number;
  isSelected: boolean;
  isMaster: boolean;
  inZone: boolean;
  inEditZone: boolean;
  stale: boolean;
  onToggle: () => void;
  onSetMaster: (deviceId: string) => void;
}

function DeviceCard({
  device,
  index,
  isSelected,
  isMaster,
  inZone,
  inEditZone,
  stale,
  onToggle,
  onSetMaster,
}: Readonly<DeviceCardProps>) {
  const { t } = useTranslation();
  const { nowPlaying, loading } = useNowPlaying(device.device_id);
  const checkId = useId();
  const badgesId = `${checkId}-badges`;
  const inOtherZone = inZone && !isSelected && !inEditZone;
  const showSlave = isSelected && !isMaster;
  const hasBadges = stale || isMaster || showSlave || inOtherZone;

  return (
    <motion.div
      className={`mr-dev${isSelected ? " mr-dev--selected" : ""}${inOtherZone ? " mr-dev--zone" : ""}${stale ? " mr-dev--stale" : ""}`}
      initial={{ y: 12 }}
      animate={{ y: 0 }}
      transition={{ delay: Math.min(index, 6) * 0.05 }}
    >
      <input
        id={checkId}
        className="mr-dev-check"
        type="checkbox"
        checked={isSelected}
        onChange={onToggle}
        disabled={inOtherZone}
        aria-describedby={hasBadges ? badgesId : undefined}
      />
      <div className="mr-dev-main">
        <label className="mr-dev-name" htmlFor={checkId}>
          {device.name}
        </label>
        <span className="mr-dev-model">{device.model}</span>
        {hasBadges && (
          <div className="mr-dev-badges" id={badgesId}>
            {stale && (
              <span
                className="ui-badge ui-badge--warning ui-badge--small"
                title={t("errors.offlineTitle")}
              >
                <span className="ui-badge-icon" aria-hidden="true">
                  {Icon.Alert(14)}
                </span>
                {t("multiroom.staleBadge")}
              </span>
            )}
            {isMaster && (
              <span className="ui-badge ui-badge--info ui-badge--small">
                <span className="ui-badge-icon mr-fill" aria-hidden="true">
                  {Icon.Star(14)}
                </span>
                {t("multiroom.masterBadge")}
              </span>
            )}
            {showSlave && (
              <span className="ui-badge ui-badge--small">
                <span className="ui-badge-icon" aria-hidden="true">
                  {Icon.Speaker(14)}
                </span>
                {t("multiroom.slaveBadge")}
              </span>
            )}
            {inOtherZone && (
              <span className="ui-badge ui-badge--small">
                <span className="ui-badge-icon" aria-hidden="true">
                  {Icon.Link(14)}
                </span>
                {t("multiroom.inZone")}
              </span>
            )}
          </div>
        )}
        <DeviceNowPlaying nowPlaying={nowPlaying} loading={loading} />
      </div>
      {showSlave && (
        <button
          type="button"
          className="btn btn-ghost btn-icon mr-star"
          onClick={() => onSetMaster(device.device_id)}
          title={t("multiroom.setMaster")}
          aria-label={t("multiroom.setMaster")}
        >
          {Icon.Star(20)}
        </button>
      )}
    </motion.div>
  );
}

// ---- Editable Zone Name ----

function EditableZoneName({
  name,
  onSave,
}: Readonly<{
  name: string;
  onSave: (newName: string) => void;
}>) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  // Esc cancels the edit; the blur that follows the unmount must not save the draft.
  const cancelledRef = useRef(false);

  const handleSave = () => {
    setEditing(false);
    if (cancelledRef.current) {
      cancelledRef.current = false;
      return;
    }
    if (draft.trim() !== name) {
      onSave(draft.trim());
    }
  };

  if (editing) {
    return (
      <h3 className="zn-title">
        <input
          className="ui-input zn-name-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={handleSave}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleSave();
            } else if (e.key === "Escape") {
              cancelledRef.current = true;
              setDraft(name);
              setEditing(false);
            }
          }}
          maxLength={30}
          autoFocus
          aria-label={t("multiroom.zoneNameEdit")}
        />
      </h3>
    );
  }

  return (
    <h3 className="zn-title">
      <button
        type="button"
        className="zn-name"
        onClick={() => {
          cancelledRef.current = false;
          setDraft(name);
          setEditing(true);
        }}
        title={t("multiroom.clickToEdit")}
      >
        <span className="zn-name-text">{name}</span>
        <span className="zn-name-icon" aria-hidden="true">
          {Icon.Pencil(16)}
        </span>
      </button>
    </h3>
  );
}

export default function MultiRoom({ devices = [] }: Readonly<MultiRoomProps>) {
  const { t } = useTranslation();
  const [dissolving, setDissolving] = useState<{ masterId: string; name: string } | null>(null);
  const {
    zones,
    isLoading,
    error,
    selectedDevices,
    editingZone,
    operationLoading,
    handleDeviceToggle,
    handleSetMaster,
    handleCreateZone: createZoneAction,
    handleDissolveZone: dissolveZoneAction,
    handleEditZone,
    cancelEdit,
    getZoneName,
    setZoneName,
  } = useZoneBuilder({
    zoneCreated: t("multiroom.zoneCreated"),
    zoneUpdated: t("multiroom.zoneUpdated"),
    zoneCreateFailed: t("multiroom.zoneCreateFailed"),
    zoneDissolved: t("multiroom.zoneDissolved"),
    zoneDissolveFailed: t("multiroom.zoneDissolveFailed"),
  });

  const handleCreateZone = () => createZoneAction();
  const handleDissolveZone = (masterId: string) => dissolveZoneAction(masterId);

  const getDeviceById = (deviceId: string): Device | undefined => {
    return devices.find((d) => d.device_id === deviceId);
  };

  const isDeviceInZone = (deviceId: string): boolean => {
    return zones.some((zone) => zone.members.some((m) => m.device_id === deviceId));
  };

  /** Returns true if device was not seen in the last 24 hours */
  const isDeviceStale = (device: Device): boolean => {
    if (!device.last_seen) return false;
    const lastSeen = new Date(device.last_seen).getTime();
    return Date.now() - lastSeen > 24 * 60 * 60 * 1000;
  };

  const getMasterName = (zone: ZoneInfo): string => {
    const master = zone.members.find((m) => m.role === "master");
    return master?.name || getDeviceById(zone.master_id)?.name || t("multiroom.unknownDevice");
  };

  const getDefaultZoneName = (zone: ZoneInfo): string =>
    t("multiroom.defaultZoneName", { name: getMasterName(zone) });

  // ---- Loading State ----
  if (isLoading && zones.length === 0) {
    return (
      <div className="mr">
        <h1 className="ui-h1">{t("multiroom.pageTitle")}</h1>
        <div className="ui-card mr-loading" role="status">
          <span className="wz-spinner" aria-hidden="true" />
          <span>{t("multiroom.loadingZones")}</span>
        </div>
        <div className="ui-card zn zn--skeleton" aria-hidden="true">
          <div className="zn-head">
            <span className="ui-skeleton zn-sk-icon" />
            <span className="ui-skeleton zn-sk-line" />
          </div>
          <span className="ui-skeleton zn-sk-block" />
        </div>
      </div>
    );
  }

  // ---- Error State ----
  if (error && zones.length === 0) {
    return (
      <div className="mr">
        <h1 className="ui-h1">{t("multiroom.pageTitle")}</h1>
        <div className="wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX(24)}
          </span>
          <div className="wz-status-body">
            <h2 className="wz-status-title">{t("multiroom.errorLoading")}</h2>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mr">
      <h1 className="ui-h1">{t("multiroom.pageTitle")}</h1>

      {/* Active Zones */}
      {zones.length > 0 && (
        <motion.section
          className="mr-section"
          aria-labelledby="mr-zones-title"
          initial={{ y: 12 }}
          animate={{ y: 0 }}
        >
          <h2 id="mr-zones-title" className="ui-h2">
            {t("multiroom.activeZones")}
          </h2>
          <div className="mr-zones">
            {zones.map((zone) => {
              const zoneName = getZoneName(zone.master_id, getDefaultZoneName(zone));

              return (
                <motion.div
                  key={zone.master_id}
                  className="ui-card zn"
                  initial={{ scale: 0.97 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="zn-head">
                    <span className="zn-icon" aria-hidden="true">
                      {Icon.Music(22)}
                    </span>
                    <EditableZoneName
                      name={zoneName}
                      onSave={(name) => setZoneName(zone.master_id, name)}
                    />
                  </div>

                  {/* Now Playing (STORY-1012) */}
                  <ZoneNowPlaying masterId={zone.master_id} />

                  {/* Zone Members with Volume (STORY-1007) */}
                  <div className="zn-members">
                    {zone.members.map((member) => (
                      <div key={member.device_id} className={`zn-member zn-member--${member.role}`}>
                        <div className="zn-member-head">
                          <span
                            className={`ui-badge ui-badge--small${member.role === "master" ? " ui-badge--info" : ""}`}
                          >
                            <span
                              className={`ui-badge-icon${member.role === "master" ? " mr-fill" : ""}`}
                              aria-hidden="true"
                            >
                              {member.role === "master" ? Icon.Star(14) : Icon.Speaker(14)}
                            </span>
                            {member.role === "master"
                              ? t("multiroom.masterBadge")
                              : t("multiroom.slaveBadge")}
                          </span>
                          <span className="zn-member-name">
                            {member.name ||
                              getDeviceById(member.device_id)?.name ||
                              t("multiroom.unknownDevice")}
                          </span>
                        </div>
                        <ZoneMemberVolume deviceId={member.device_id} />
                      </div>
                    ))}
                  </div>

                  {/* Zone Actions */}
                  <div className="zn-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleEditZone(zone)}
                      disabled={operationLoading}
                    >
                      {Icon.Pencil(18)}
                      <span>{t("multiroom.editZone")}</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger-outline"
                      onClick={() => setDissolving({ masterId: zone.master_id, name: zoneName })}
                      disabled={operationLoading}
                    >
                      {Icon.Unlink(18)}
                      <span>{t("multiroom.dissolve")}</span>
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.section>
      )}

      {/* Empty State */}
      {zones.length === 0 && (
        <motion.div className="wz-status mr-info" initial={{ y: 8 }} animate={{ y: 0 }}>
          <span className="wz-icon" aria-hidden="true">
            {Icon.Info(24)}
          </span>
          <div className="wz-status-body">
            <h2 className="mr-info-title">{t("multiroom.noActiveZones")}</h2>
            <p>{t("multiroom.noActiveZonesHint")}</p>
          </div>
        </motion.div>
      )}

      {/* Device Selection */}
      <motion.section
        className="mr-section"
        aria-labelledby="mr-select-title"
        initial={{ y: 12 }}
        animate={{ y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h2 id="mr-select-title" className="ui-h2">
          {editingZone
            ? t("multiroom.editTitle", {
                name: getZoneName(editingZone.master_id, getDefaultZoneName(editingZone)),
              })
            : t("multiroom.newTitle")}
        </h2>

        <div className="mr-grid" role="group" aria-labelledby="mr-select-title">
          {devices.map((device, index) => {
            const inZone = isDeviceInZone(device.device_id);
            const isSelected = selectedDevices.includes(device.device_id);
            const isMaster = selectedDevices[0] === device.device_id;
            const inEditZone =
              editingZone?.members.some((m) => m.device_id === device.device_id) ?? false;
            const stale = isDeviceStale(device);

            return (
              <DeviceCard
                key={device.device_id}
                device={device}
                index={index}
                isSelected={isSelected}
                isMaster={isMaster}
                inZone={inZone}
                inEditZone={inEditZone}
                stale={stale}
                onToggle={() => handleDeviceToggle(device.device_id)}
                onSetMaster={handleSetMaster}
              />
            );
          })}
        </div>

        {selectedDevices.length > 0 && (
          <motion.div className="mr-bar" initial={{ y: 10 }} animate={{ y: 0 }}>
            <p className="mr-bar-count" role="status">
              {selectedDevices.length < 2
                ? t("multiroom.selectedCountMin", { count: selectedDevices.length })
                : t("multiroom.selectedCount", { count: selectedDevices.length })}
            </p>
            <div className="mr-bar-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCreateZone}
                disabled={selectedDevices.length < 2 || operationLoading}
                aria-busy={operationLoading || undefined}
              >
                {operationLoading ? (
                  <span className="ui-spin">{Icon.Loader(18)}</span>
                ) : (
                  Icon.Plus(18)
                )}
                <span>
                  {operationLoading
                    ? t("multiroom.creating")
                    : editingZone
                      ? t("multiroom.updateZone")
                      : t("multiroom.createZone")}
                </span>
              </button>
              {editingZone && (
                <button type="button" className="btn btn-secondary" onClick={cancelEdit}>
                  {t("multiroom.cancel")}
                </button>
              )}
            </div>
          </motion.div>
        )}
      </motion.section>

      {/* Info Box */}
      <motion.div
        className="wz-status mr-info"
        initial={{ y: 8 }}
        animate={{ y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <span className="wz-icon" aria-hidden="true">
          {Icon.Info(24)}
        </span>
        <div className="wz-status-body">
          <h2 className="mr-info-title">{t("multiroom.infoTitle")}</h2>
          <ul className="mr-info-list">
            <li>{t("multiroom.infoItem1")}</li>
            <li>{t("multiroom.infoItem2")}</li>
            <li>{t("multiroom.infoItem3")}</li>
            <li>{t("multiroom.infoItem4")}</li>
            <li>{t("multiroom.infoItem5")}</li>
          </ul>
        </div>
      </motion.div>

      {/* Confirm Dissolve Dialog */}
      <ConfirmDialog
        open={dissolving !== null}
        title={t("multiroom.confirmDissolveTitle")}
        message={t("multiroom.confirmDissolveMessage", { name: dissolving?.name })}
        confirmLabel={t("multiroom.dissolve")}
        cancelLabel={t("multiroom.cancel")}
        destructive
        onConfirm={() => {
          const masterId = dissolving?.masterId;
          setDissolving(null);
          if (masterId) handleDissolveZone(masterId);
        }}
        onCancel={() => setDissolving(null)}
      />
    </div>
  );
}

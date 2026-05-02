import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Device } from "../components/DeviceSwiper";
import { useZoneBuilder } from "../hooks/useZoneBuilder";
import { useVolume } from "../hooks/useVolume";
import { useNowPlaying } from "../hooks/useNowPlaying";
import type { ZoneInfo } from "../api/zones";
import VolumeSlider from "../components/VolumeSlider";
import NowPlaying from "../components/NowPlaying";
import "./MultiRoom.css";

interface MultiRoomProps {
  readonly devices?: Device[];
}

// ---- Zone icon SVG (lighter color for dark card backgrounds) ----
const ZONE_MUSIC_PATH =
  "M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z";

function ZoneIcon() {
  return (
    <span className="zone-icon">
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <path fill="#7ab8e8" d={ZONE_MUSIC_PATH} />
      </svg>
    </span>
  );
}

// ---- Zone Volume per Member ----

function ZoneMemberVolume({ deviceId }: Readonly<{ deviceId: string }>) {
  const { volume, muted, setDeviceVolume, toggleMute } = useVolume(deviceId);
  return (
    <div className="zone-member-volume">
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
    return <div className="zone-now-playing standby">{t("multiroom.standby")}</div>;
  }
  return (
    <div className="zone-now-playing">
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

  const handleSave = () => {
    setEditing(false);
    if (draft.trim() !== name) {
      onSave(draft.trim());
    }
  };

  if (editing) {
    return (
      <input
        className="zone-name-input"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={handleSave}
        onKeyDown={(e) => e.key === "Enter" && handleSave()}
        maxLength={30}
        autoFocus
        aria-label={t("multiroom.zoneNameEdit")}
      />
    );
  }

  return (
    <button
      type="button"
      className="zone-name editable"
      onClick={() => {
        setDraft(name);
        setEditing(true);
      }}
      title={t("multiroom.clickToEdit")}
    >
      {name}
    </button>
  );
}

export default function MultiRoom({ devices = [] }: Readonly<MultiRoomProps>) {
  const { t } = useTranslation();
  const {
    zones,
    isLoading,
    error,
    selectedDevices,
    editingZone,
    operationLoading,
    confirmDissolve,
    setConfirmDissolve,
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
    return master?.name || getDeviceById(zone.master_id)?.name || "Unknown";
  };

  // ---- Loading State ----
  if (isLoading && zones.length === 0) {
    return (
      <div className="page multiroom-page">
        <h1 className="page-title">{t("multiroom.pageTitle")}</h1>
        <div className="zone-card" style={{ opacity: 0.5 }}>
          <div className="zone-header">
            <ZoneIcon />
            <h3 className="zone-name">{t("multiroom.loadingZones")}</h3>
          </div>
        </div>
      </div>
    );
  }

  // ---- Error State ----
  if (error && zones.length === 0) {
    return (
      <div className="page multiroom-page">
        <h1 className="page-title">{t("multiroom.pageTitle")}</h1>
        <div className="info-box" style={{ borderColor: "#ff6b6b" }}>
          <div className="info-icon">⚠️</div>
          <div className="info-content">
            <h4 className="info-title">{t("multiroom.errorLoading")}</h4>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page multiroom-page">
      <h1 className="page-title">{t("multiroom.pageTitle")}</h1>

      {/* Active Zones */}
      {zones.length > 0 && (
        <motion.section
          className="zones-section"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h2 className="section-title">{t("multiroom.activeZones")}</h2>
          <div className="zones-list">
            {zones.map((zone) => {
              const defaultName = `${getMasterName(zone)} Zone`;
              const zoneName = getZoneName(zone.master_id, defaultName);

              return (
                <motion.div
                  key={zone.master_id}
                  className="zone-card"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="zone-header">
                    <ZoneIcon />
                    <EditableZoneName
                      name={zoneName}
                      onSave={(name) => setZoneName(zone.master_id, name)}
                    />
                  </div>

                  {/* Now Playing (STORY-1012) */}
                  <ZoneNowPlaying masterId={zone.master_id} />

                  {/* Zone Members with Volume (STORY-1007) */}
                  <div className="zone-devices">
                    {zone.members.map((member) => (
                      <div key={member.device_id} className={`zone-device ${member.role}`}>
                        <div className="zone-device-header">
                          <span className={`device-badge ${member.role}-badge`}>
                            {member.role === "master"
                              ? t("multiroom.masterBadge")
                              : t("multiroom.slaveBadge")}
                          </span>
                          <span className="device-name">
                            {member.name ||
                              getDeviceById(member.device_id)?.name ||
                              "Unknown Device"}
                          </span>
                        </div>
                        <ZoneMemberVolume deviceId={member.device_id} />
                      </div>
                    ))}
                  </div>

                  {/* Zone Actions */}
                  <div className="zone-actions">
                    <button
                      className="zone-action-button edit"
                      onClick={() => handleEditZone(zone)}
                      disabled={operationLoading}
                    >
                      <span className="button-icon">✏️</span>
                      <span>{t("multiroom.editZone")}</span>
                    </button>
                    {confirmDissolve === zone.master_id ? (
                      <button
                        className="zone-action-button dissolve"
                        onClick={() => handleDissolveZone(zone.master_id)}
                        disabled={operationLoading}
                      >
                        <span className="button-icon">⚠️</span>
                        <span>{t("multiroom.dissolveConfirm")}</span>
                      </button>
                    ) : (
                      <button
                        className="zone-action-button dissolve"
                        onClick={() => setConfirmDissolve(zone.master_id)}
                        disabled={operationLoading}
                      >
                        <span className="button-icon">❌</span>
                        <span>{t("multiroom.dissolve")}</span>
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.section>
      )}

      {/* Empty State */}
      {zones.length === 0 && (
        <motion.div className="info-box" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="info-icon">ℹ️</div>
          <div className="info-content">
            <h4 className="info-title">{t("multiroom.noActiveZones")}</h4>
            <p>{t("multiroom.noActiveZonesHint")}</p>
          </div>
        </motion.div>
      )}

      {/* Device Selection */}
      <motion.section
        className="device-selection-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h2 className="section-title">
          {editingZone
            ? `${t("multiroom.editTitle")}: ${getZoneName(editingZone.master_id, getMasterName(editingZone) + " Zone")}`
            : t("multiroom.newTitle")}
        </h2>

        <div className="devices-grid">
          {devices.map((device, index) => {
            const inZone = isDeviceInZone(device.device_id);
            const isSelected = selectedDevices.includes(device.device_id);
            const isMaster = selectedDevices[0] === device.device_id;
            const inEditZone =
              editingZone?.members.some((m) => m.device_id === device.device_id) ?? false;
            const stale = isDeviceStale(device);

            return (
              <motion.label
                key={device.device_id}
                className={`device-checkbox-card ${isSelected ? "selected" : ""} ${inZone && !isSelected && !inEditZone ? "in-zone" : ""} ${stale ? "stale" : ""}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => handleDeviceToggle(device.device_id)}
                  disabled={inZone && !isSelected && !inEditZone}
                />
                <div className="device-checkbox-content">
                  <div className="device-checkbox-header">
                    <span className="device-checkbox-name">{device.name}</span>
                    {stale && (
                      <span className="device-badge stale-badge" title={t("errors.offlineTitle")}>
                        ⚠️
                      </span>
                    )}
                    {isMaster && (
                      <span className="device-badge master-badge">
                        {t("multiroom.masterBadge")}
                      </span>
                    )}
                    {isSelected && !isMaster && (
                      <>
                        <span className="device-badge slave-badge">
                          {t("multiroom.slaveBadge")}
                        </span>
                        <button
                          className="set-master-btn"
                          onClick={(e) => {
                            e.preventDefault();
                            handleSetMaster(device.device_id);
                          }}
                          title={t("multiroom.setMaster")}
                        >
                          ★
                        </button>
                      </>
                    )}
                    {inZone && !isSelected && !inEditZone && (
                      <span className="device-badge in-zone-badge">{t("multiroom.inZone")}</span>
                    )}
                  </div>
                  <span className="device-checkbox-model">{device.model}</span>
                </div>
              </motion.label>
            );
          })}
        </div>

        {selectedDevices.length > 0 && (
          <motion.div
            className="selection-info"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <p className="selection-count">
              {selectedDevices.length < 2
                ? t("multiroom.selectedCountMin", { count: selectedDevices.length })
                : t("multiroom.selectedCount", { count: selectedDevices.length })}
            </p>
            <button
              className="create-zone-button"
              onClick={handleCreateZone}
              disabled={selectedDevices.length < 2 || operationLoading}
            >
              <span className="button-icon">{operationLoading ? "⏳" : "➕"}</span>
              <span>
                {operationLoading
                  ? t("multiroom.creating")
                  : editingZone
                    ? t("multiroom.updateZone")
                    : t("multiroom.createZone")}
              </span>
            </button>
            {editingZone && (
              <button className="zone-action-button" onClick={cancelEdit}>
                {t("multiroom.cancel")}
              </button>
            )}
          </motion.div>
        )}
      </motion.section>

      {/* Info Box */}
      <motion.div
        className="info-box"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <div className="info-icon">ℹ️</div>
        <div className="info-content">
          <h4 className="info-title">{t("multiroom.infoTitle")}</h4>
          <ul className="info-list">
            <li>{t("multiroom.infoItem1")}</li>
            <li>{t("multiroom.infoItem2")}</li>
            <li>{t("multiroom.infoItem3")}</li>
            <li>{t("multiroom.infoItem4")}</li>
            <li>{t("multiroom.infoItem5")}</li>
          </ul>
        </div>
      </motion.div>
    </div>
  );
}

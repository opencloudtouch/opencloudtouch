import { useState } from "react";
import { motion } from "framer-motion";
import "./MultiRoom.css";

const MOCK_ZONES = [
  {
    id: "zone_1",
    name: "Living Room Zone",
    master: "aabbcc112233",
    slaves: ["ddeeff445566"],
  },
];

export default function MultiRoom({ devices = [] }) {
  const [zones, setZones] = useState(MOCK_ZONES);
  const [selectedDevices, setSelectedDevices] = useState([]);
  const [editingZone, setEditingZone] = useState(null);

  const handleDeviceToggle = (deviceId) => {
    setSelectedDevices((prev) => {
      if (prev.includes(deviceId)) {
        return prev.filter((id) => id !== deviceId);
      }
      return [...prev, deviceId];
    });
  };

  const handleCreateZone = () => {
    if (selectedDevices.length < 2) {
      alert("Mindestens 2 Geräte erforderlich für eine Zone");
      return;
    }

    const newZone = {
      id: `zone_${Date.now()}`,
      name: `Neue Zone ${zones.length + 1}`,
      master: selectedDevices[0],
      slaves: selectedDevices.slice(1),
    };

    setZones([...zones, newZone]);
    setSelectedDevices([]);
  };

  const handleDissolveZone = (zoneId) => {
    setZones(zones.filter((z) => z.id !== zoneId));
  };

  const handleEditZone = (zone) => {
    setEditingZone(zone);
    setSelectedDevices([zone.master, ...zone.slaves]);
  };

  const getDeviceById = (deviceId) => {
    return devices.find((d) => d.device_id === deviceId);
  };

  const isDeviceInZone = (deviceId) => {
    return zones.some(
      (zone) => zone.master === deviceId || zone.slaves.includes(deviceId),
    );
  };

  return (
    <div className="page multiroom-page">
      <h1 className="page-title">Multi-Room Zonen</h1>

      {/* Active Zones */}
      {zones.length > 0 && (
        <motion.section
          className="zones-section"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h2 className="section-title">Aktive Zonen</h2>
          <div className="zones-list">
            {zones.map((zone) => {
              const masterDevice = getDeviceById(zone.master);
              const slaveDevices = zone.slaves
                .map((id) => getDeviceById(id))
                .filter(Boolean);

              return (
                <motion.div
                  key={zone.id}
                  className="zone-card"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="zone-header">
                    <span className="zone-icon">🎵</span>
                    <h3 className="zone-name">{zone.name}</h3>
                  </div>

                  <div className="zone-devices">
                    <div className="zone-device master">
                      <span className="device-badge master-badge">Master</span>
                      <span className="device-name">
                        {masterDevice?.name || "Unknown"}
                      </span>
                    </div>

                    {slaveDevices.map((device) => (
                      <div key={device.device_id} className="zone-device slave">
                        <span className="device-badge slave-badge">Slave</span>
                        <span className="device-name">{device.name}</span>
                      </div>
                    ))}
                  </div>

                  <div className="zone-actions">
                    <button
                      className="zone-action-button edit"
                      onClick={() => handleEditZone(zone)}
                    >
                      <span className="button-icon">✏️</span>
                      <span>Bearbeiten</span>
                    </button>
                    <button
                      className="zone-action-button dissolve"
                      onClick={() => handleDissolveZone(zone.id)}
                    >
                      <span className="button-icon">❌</span>
                      <span>Auflösen</span>
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.section>
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
            ? `Zone bearbeiten: ${editingZone.name}`
            : "Neue Zone erstellen"}
        </h2>

        <div className="devices-grid">
          {devices.map((device, index) => {
            const inZone = isDeviceInZone(device.device_id);
            const isSelected = selectedDevices.includes(device.device_id);
            const isMaster = selectedDevices[0] === device.device_id;

            return (
              <motion.label
                key={device.device_id}
                className={`device-checkbox-card ${isSelected ? "selected" : ""} ${inZone && !isSelected ? "in-zone" : ""}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => handleDeviceToggle(device.device_id)}
                  disabled={inZone && !isSelected}
                />
                <div className="device-checkbox-content">
                  <div className="device-checkbox-header">
                    <span className="device-checkbox-name">{device.name}</span>
                    {isMaster && (
                      <span className="device-badge master-badge">Master</span>
                    )}
                    {isSelected && !isMaster && (
                      <span className="device-badge slave-badge">Slave</span>
                    )}
                    {inZone && !isSelected && (
                      <span className="device-badge in-zone-badge">
                        In Zone
                      </span>
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
              {selectedDevices.length} Gerät(e) ausgewählt
              {selectedDevices.length < 2 && " (mindestens 2 erforderlich)"}
            </p>
            <button
              className="create-zone-button"
              onClick={handleCreateZone}
              disabled={selectedDevices.length < 2}
            >
              <span className="button-icon">➕</span>
              <span>
                {editingZone ? "Zone aktualisieren" : "Zone erstellen"}
              </span>
            </button>
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
          <h4 className="info-title">Multi-Room Hinweise</h4>
          <ul className="info-list">
            <li>Das erste ausgewählte Gerät wird automatisch zum Master</li>
            <li>Alle weiteren Geräte werden als Slaves hinzugefügt</li>
            <li>Master und Slaves spielen synchron die gleiche Musik</li>
            <li>Lautstärke kann pro Gerät individuell angepasst werden</li>
          </ul>
        </div>
      </motion.div>
    </div>
  );
}

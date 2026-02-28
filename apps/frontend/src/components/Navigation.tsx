import { NavLink, useSearchParams } from "react-router-dom";
import "./Navigation.css";

export default function Navigation() {
  const [searchParams] = useSearchParams();
  const deviceParam = searchParams.get("device");

  // Preserve device parameter across all navigation
  const withDevice = (path: string) => {
    if (!deviceParam) return path;
    return `${path}?device=${deviceParam}`;
  };

  return (
    <nav className="nav">
      <div className="nav-container">
        <NavLink to={withDevice("/")} className="nav-link">
          <span className="nav-icon">📻</span>
          <span className="nav-label">Presets</span>
        </NavLink>
        {/* <NavLink to={withDevice("/local")} className="nav-link">
          <span className="nav-icon">🎵</span>
          <span className="nav-label">Control</span>
        </NavLink>
        <NavLink to={withDevice("/multiroom")} className="nav-link">
          <span className="nav-icon">🔊</span>
          <span className="nav-label">Zones</span>
        </NavLink>
        <NavLink to={withDevice("/firmware")} className="nav-link">
          <span className="nav-icon">⚙️</span>
          <span className="nav-label">Firmware</span>
        </NavLink> */}
        <NavLink to={withDevice("/settings")} className="nav-link">
          <span className="nav-icon">⚡</span>
          <span className="nav-label">Settings</span>
        </NavLink>
      </div>
    </nav>
  );
}

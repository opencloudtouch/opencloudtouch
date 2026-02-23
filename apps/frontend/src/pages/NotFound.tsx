/**
 * 404 Not Found Page
 */
import { useNavigate } from "react-router-dom";
import "./NotFound.css";

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="not-found-container">
      <div className="not-found-content">
        <h1 className="not-found-code">404</h1>
        <h2 className="not-found-title">Seite nicht gefunden</h2>
        <p className="not-found-description">
          Die angeforderte Seite existiert nicht oder wurde verschoben.
        </p>
        <button className="btn btn-primary" onClick={() => navigate("/")}>
          Zurück zur Startseite
        </button>
      </div>
    </div>
  );
}

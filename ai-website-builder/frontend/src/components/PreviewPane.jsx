import { useState } from "react";
import Folder from "./Folder";
import "./PreviewPane.css";

const DEVICES = {
  desktop: { width: "100%", label: "Desktop" },
  tablet: { width: "768px", label: "Tablet" },
  mobile: { width: "390px", label: "Mobile" },
};

export default function PreviewPane({ html, onRefresh, onExport, empty }) {
  const [device, setDevice] = useState("desktop");
  const [fullscreen, setFullscreen] = useState(false);

  return (
    <div className={`preview-pane ${fullscreen ? "is-fullscreen" : ""}`}>
      <div className="preview-toolbar">
        <div className="device-toggle">
          {Object.entries(DEVICES).map(([key, d]) => (
            <button
              key={key}
              className={device === key ? "active" : ""}
              onClick={() => setDevice(key)}
              type="button"
            >
              {d.label}
            </button>
          ))}
        </div>
        <div className="preview-actions">
          <button className="btn" type="button" onClick={onRefresh}>Refresh</button>
          <button className="btn" type="button" onClick={() => setFullscreen((f) => !f)}>
            {fullscreen ? "Exit fullscreen" : "Fullscreen"}
          </button>
          <button className="btn btn-primary" type="button" onClick={onExport} disabled={empty}>
            Export ZIP
          </button>
        </div>
      </div>
      <div className="preview-frame-wrap">
        {empty ? (
          <div className="preview-empty preview-empty-enhanced">
            <Folder
              size={1.35}
              color="#8b5cf6"
              items={[
                <span key="layout">LAYOUT</span>,
                <span key="content">CONTENT</span>,
                <span key="launch">LAUNCH</span>,
              ]}
            />
            <span>Generate a website to open your live preview.</span>
          </div>
        ) : (
          <div className="preview-frame-shell" style={{ width: DEVICES[device].width }}>
            <iframe
              title="Generated website preview"
              srcDoc={html}
              sandbox="allow-scripts"
              className="preview-frame"
            />
          </div>
        )}
      </div>
    </div>
  );
}

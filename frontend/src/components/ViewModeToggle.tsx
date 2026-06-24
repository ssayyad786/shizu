export type ViewMode = "mobile" | "desktop";

const STORAGE_KEY = "shizu-view-mode";

export function getDefaultViewMode(): ViewMode {
  if (typeof window === "undefined") return "desktop";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "mobile" || stored === "desktop") return stored;
  return window.innerWidth < 768 ? "mobile" : "desktop";
}

export function saveViewMode(mode: ViewMode) {
  localStorage.setItem(STORAGE_KEY, mode);
}

interface Props {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export default function ViewModeToggle({ mode, onChange }: Props) {
  return (
    <div className="view-mode-toggle" role="group" aria-label="Layout mode">
      <button
        type="button"
        className={`view-mode-btn ${mode === "mobile" ? "active" : ""}`}
        onClick={() => onChange("mobile")}
        title="Mobile layout"
      >
        📱 Mobile
      </button>
      <button
        type="button"
        className={`view-mode-btn ${mode === "desktop" ? "active" : ""}`}
        onClick={() => onChange("desktop")}
        title="Desktop layout"
      >
        🖥 Desktop
      </button>
    </div>
  );
}

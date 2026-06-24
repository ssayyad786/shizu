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
  compact?: boolean;
}

export default function ViewModeToggle({ mode, onChange, compact }: Props) {
  return (
    <div
      className={`view-mode-toggle ${compact ? "view-mode-toggle-compact" : ""}`}
      role="group"
      aria-label="Layout mode"
    >
      <button
        type="button"
        className={`view-mode-btn ${mode === "mobile" ? "active" : ""}`}
        onClick={() => onChange("mobile")}
        title="Mobile layout"
        aria-label="Mobile layout"
      >
        {compact ? "📱" : "📱 Mobile"}
      </button>
      <button
        type="button"
        className={`view-mode-btn ${mode === "desktop" ? "active" : ""}`}
        onClick={() => onChange("desktop")}
        title="Desktop layout"
        aria-label="Desktop layout"
      >
        {compact ? "🖥" : "🖥 Desktop"}
      </button>
    </div>
  );
}

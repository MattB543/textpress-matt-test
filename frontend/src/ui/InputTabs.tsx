type Mode = "file" | "text" | "url";

export function InputTabs({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <div className="tabs">
      <button
        className={`tab-btn ${mode === "file" ? "active" : ""}`}
        onClick={() => onChange("file")}
      >
        File
      </button>
      <button
        className={`tab-btn ${mode === "text" ? "active" : ""}`}
        onClick={() => onChange("text")}
      >
        Text
      </button>
      <button
        className={`tab-btn ${mode === "url" ? "active" : ""}`}
        onClick={() => onChange("url")}
      >
        URL
      </button>
    </div>
  );
}

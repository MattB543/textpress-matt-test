type Mode = "file" | "text" | "url" | "combine";

export function InputTabs({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <div className="tabs" role="tablist" aria-label="Input mode">
      <button
        className={`tab-btn ${mode === "file" ? "active" : ""}`}
        role="tab"
        aria-selected={mode === "file"}
        onClick={() => onChange("file")}
      >
        Upload File
      </button>
      <button
        className={`tab-btn ${mode === "url" ? "active" : ""}`}
        role="tab"
        aria-selected={mode === "url"}
        onClick={() => onChange("url")}
      >
        Paste URL
      </button>
      <button
        className={`tab-btn ${mode === "text" ? "active" : ""}`}
        role="tab"
        aria-selected={mode === "text"}
        onClick={() => onChange("text")}
      >
        Paste Text
      </button>
      <button
        className={`tab-btn ${mode === "combine" ? "active" : ""}`}
        role="tab"
        aria-selected={mode === "combine"}
        onClick={() => onChange("combine")}
      >
        Combine Reports
      </button>
    </div>
  );
}

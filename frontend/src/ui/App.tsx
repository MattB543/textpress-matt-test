import { useCallback, useEffect, useRef, useState } from "react";
import { DropZone } from "./DropZone";
import { InputTabs } from "./InputTabs";
import { api } from "../utils/api";

export function App() {
  type Mode = "file" | "text" | "url";
  const [mode, setMode] = useState<Mode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publicUrl, setPublicUrl] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const reset = () => {
    setError(null);
    setPublicUrl(null);
  };

  async function onSubmit() {
    reset();
    try {
      console.log("[App] onSubmit start", { mode });
      // Validate based on selected mode
      if (mode === "file") {
        if (!file) throw new Error("Please select a .docx/.md/.txt file");
        if (file.size > 15 * 1024 * 1024)
          throw new Error("File too large (max 15MB)");
      } else if (mode === "text") {
        if (!text.trim()) throw new Error("Please paste or type some text");
        if (text.length > 2_000_000)
          throw new Error("Text too long (max ~2MB)");
      } else if (mode === "url") {
        if (!url.trim()) throw new Error("Please enter a URL");
        try {
          new URL(url);
        } catch {
          throw new Error("Invalid URL");
        }
      }

      setBusy(true);
      const res = await api.convert({ file, text, url });
      setPublicUrl(res.public_url);
      console.log("[App] convert success", res);
    } catch (e: any) {
      setError(e?.message ?? "Something went wrong");
      console.error("[App] convert error", e);
    } finally {
      setBusy(false);
      console.log("[App] onSubmit end");
    }
  }

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.max(el.scrollHeight, 160) + "px";
  }, []);

  useEffect(() => {
    autoResize();
  }, [text, autoResize]);

  return (
    <>
      <div className="textpress-header">
        <div className="inner">
          <div className="logo">
            Text<span className="accent">press</span>
          </div>
          <div className="tagline">Simple publishing for complex docs</div>
        </div>
      </div>

      <div className="container">
        <div className="tabs-panel">
          <InputTabs mode={mode} onChange={setMode} />
          <div className="panel">
            {mode === "url" && (
              <input
                className="input"
                placeholder="https://example.com/article.html"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            )}
            {mode === "file" && (
              <div>
                <DropZone
                  onFile={setFile}
                  accept={[".docx", ".md", ".markdown", ".txt"]}
                />
                {file && (
                  <div className="muted" style={{ marginTop: 6 }}>
                    Selected: {file.name}
                  </div>
                )}
              </div>
            )}
            {mode === "text" && (
              <textarea
                ref={textareaRef}
                className="textarea"
                placeholder="Paste or type your text or Markdown..."
                value={text}
                onChange={(e) => setText(e.target.value)}
                onInput={autoResize}
                style={{ overflow: "hidden" }}
              />
            )}
          </div>
        </div>

        <div className="row cta">
          <button
            className="btn btn-primary"
            onClick={onSubmit}
            disabled={busy}
          >
            {busy ? "Converting…" : "Convert & Publish"}
          </button>
        </div>

        <div className="spacer" />

        {error && <div className="error">{error}</div>}
        {publicUrl && (
          <div className="result">
            Published!{" "}
            <a href={publicUrl} target="_blank" rel="noreferrer">
              Open link
            </a>
          </div>
        )}
      </div>
    </>
  );
}

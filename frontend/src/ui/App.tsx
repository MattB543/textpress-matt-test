import { useState } from "react";
import { DropZone } from "./DropZone";
import { InputTabs } from "./InputTabs";
import { api } from "../utils/api";

type Mode = "file" | "text" | "url";

export function App() {
  const [mode, setMode] = useState<Mode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publicUrl, setPublicUrl] = useState<string | null>(null);

  const reset = () => {
    setError(null);
    setPublicUrl(null);
  };

  async function onSubmit() {
    reset();
    try {
      // Basic client-side validation
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
    } catch (e: any) {
      setError(e?.message ?? "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <header>
        <div className="title">Textpress</div>
        <div className="subtitle">Simple publishing for complex docs</div>
      </header>

      <div className="card">
        <InputTabs mode={mode} onChange={setMode} />

        <div className="grid">
          {mode === "file" && (
            <DropZone
              onFile={setFile}
              accept={[".docx", ".md", ".markdown", ".txt"]}
            />
          )}

          {mode === "text" && (
            <textarea
              className="textarea"
              placeholder="Paste or type your text or Markdown..."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          )}

          {mode === "url" && (
            <input
              className="input"
              placeholder="https://example.com/article.html"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          )}
        </div>

        <div className="spacer" />

        <div className="row">
          <button className="button" onClick={onSubmit} disabled={busy}>
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
    </div>
  );
}

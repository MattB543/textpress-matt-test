import { useCallback, useEffect, useState } from "react";
import { DropZone } from "./DropZone";
import { api } from "../utils/api";

type UploadStatus = "waiting" | "uploading" | "complete" | "error";

type UploadState = {
  id: number;
  file: File | null;
  status: UploadStatus;
  docId: string | null;
  title?: string | null;
};

export interface CombineResult {
  id: string;
  public_url: string;
  component_ids: string[];
}

export function CombineReports({
  onComplete,
}: {
  onComplete: (result: CombineResult) => void;
}) {
  const [uploads, setUploads] = useState<UploadState[]>([
    { id: 1, file: null, status: "waiting", docId: null },
    { id: 2, file: null, status: "waiting", docId: null },
    { id: 3, file: null, status: "waiting", docId: null },
  ]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [combinedTitle, setCombinedTitle] = useState(
    "Combined Research Report"
  );

  const updateUpload = useCallback(
    (index: number, patch: Partial<UploadState>) => {
      setUploads((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], ...patch };
        return next;
      });
    },
    []
  );

  async function handleFileUpload(index: number, file: File) {
    setError(null);
    updateUpload(index, { file, status: "uploading" });
    try {
      const result = await api.convert({ file });
      updateUpload(index, {
        status: "complete",
        docId: result.id,
        title: file.name,
      });
    } catch (e: any) {
      updateUpload(index, { status: "error" });
      setError(e?.message ?? "Upload failed");
      return;
    }
  }

  async function combineIfReady() {
    if (!uploads.every((u) => u.status === "complete" && u.docId)) return;
    setBusy(true);
    setError(null);
    try {
      const docIds = uploads.map((u) => u.docId!) as string[];
      const titles = uploads.map((u, i) => u.title || `Report ${i + 1}`);
      const result = await api.combine({
        doc_ids: docIds,
        titles,
        combined_title: combinedTitle,
      });
      onComplete(result);
    } catch (e: any) {
      setError(e?.message ?? "Combine failed");
    } finally {
      setBusy(false);
    }
  }

  // Auto-combine when all uploads complete
  useEffect(() => {
    if (busy) return;
    if (uploads.every((u) => u.status === "complete" && u.docId)) {
      void combineIfReady();
    }
  }, [uploads, busy]);

  return (
    <div className="combine-container">
      <div className="muted" style={{ marginBottom: 8 }}>
        Upload three reports. Combining will start automatically.
      </div>
      <div className="upload-grid">
        {uploads.map((upload, idx) => (
          <div key={idx} className="upload-slot">
            <label style={{ fontWeight: 600 }}>Report {idx + 1}</label>
            <DropZone onFile={(file) => handleFileUpload(idx, file)} />
            <div className="muted" style={{ marginTop: 6 }}>
              {upload.status === "waiting" && "Waiting"}
              {upload.status === "uploading" && (
                <>
                  Uploading…
                  <div className="progress-bar" aria-label="Uploading">
                    <div className="progress-fill" />
                  </div>
                </>
              )}
              {upload.status === "complete" && (upload.title || "Ready")}
              {upload.status === "error" && (
                <>
                  Error
                  <button
                    onClick={() =>
                      updateUpload(idx, {
                        status: "waiting",
                        file: null,
                        docId: null,
                      })
                    }
                    className="btn btn-sm"
                    style={{ marginLeft: 8 }}
                  >
                    Retry
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 12 }}>
        <input
          className="input"
          placeholder="Combined title"
          value={combinedTitle}
          onChange={(e) => setCombinedTitle(e.target.value)}
        />
      </div>

      <div className="combine-status" style={{ marginTop: 12 }}>
        {uploads.filter((u) => u.status === "complete").length} of 3 reports
        uploaded
      </div>

      {!uploads.every((u) => u.status === "complete") && (
        <div className="row cta" style={{ marginTop: 12 }}>
          <button className="btn btn-primary" disabled>
            Waiting for uploads…
          </button>
        </div>
      )}

      {error && (
        <div className="error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}
    </div>
  );
}

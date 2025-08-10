import { useCallback, useRef, useState } from "react";

type Props = {
  onFile: (file: File) => void;
  accept?: string[];
};

export function DropZone({ onFile, accept }: Props) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDrag(false);
      const f = e.dataTransfer.files?.[0];
      console.log("[DropZone] onDrop", {
        hasFile: !!f,
        name: f?.name,
        size: f?.size,
      });
      if (f) onFile(f);
    },
    [onFile]
  );

  const onSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      console.log("[DropZone] onSelect", {
        hasFile: !!f,
        name: f?.name,
        size: f?.size,
      });
      if (f) onFile(f);
    },
    [onFile]
  );

  return (
    <div>
      <div
        className={`drop ${drag ? "drag" : ""}`}
        onDragEnter={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDrag(false);
        }}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div style={{ fontWeight: 600, marginBottom: 6 }}>
          Drag & drop your file
        </div>
        <div className="muted">Accepted: .docx, .md, .txt</div>
      </div>
      <input
        ref={inputRef}
        className="hidden"
        type="file"
        style={{ display: "none" }}
        accept={accept?.join(",")}
        onChange={onSelect}
      />
    </div>
  );
}

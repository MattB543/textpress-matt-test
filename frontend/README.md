# Textpress Frontend

Minimal web UI for Textpress MVP.

Features:

- Drag & drop file upload (docx/md/txt), Text input, or URL input.
- Calls backend `POST /api/convert` and shows the published public URL.

Dev:

```sh
pnpm i   # or npm i / yarn
pnpm dev # http://localhost:5173
```

Proxy is configured in `vite.config.ts` to forward `/api/*` to `http://localhost:8000`.

Build:

```sh
pnpm build
pnpm preview
```

const API_BASE: string = (import.meta as any).env?.VITE_API_BASE || "/api";
console.log("[api] API_BASE:", API_BASE);

export const api = {
  async convert({
    file,
    text,
    url,
  }: {
    file?: File | null;
    text?: string;
    url?: string;
  }): Promise<{ id: string; public_url: string }> {
    const form = new FormData();
    if (file) form.append("file", file);
    if (text) form.append("text", text);
    if (url) form.append("url", url);

    console.log("[api.convert] start", {
      hasFile: !!file,
      textLen: text?.length ?? 0,
      url: url ? url.substring(0, 200) : undefined,
    });
    const res = await fetch(`${API_BASE}/convert`, {
      method: "POST",
      body: form,
    });
    console.log("[api.convert] response", res.status, res.statusText);
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try {
        const data = await res.json();
        if (data?.error) msg = data.error;
        console.error("[api.convert] error payload", data);
      } catch (e) {
        console.error("[api.convert] failed to parse error json", e);
      }
      throw new Error(msg);
    }
    const json = await res.json();
    console.log("[api.convert] success payload", json);
    return json;
  },
};

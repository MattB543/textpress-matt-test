const API_BASE: string = (import.meta as any).env?.VITE_API_BASE || "/api";

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

    const res = await fetch(`${API_BASE}/convert`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try {
        const data = await res.json();
        if (data?.error) msg = data.error;
      } catch {}
      throw new Error(msg);
    }
    return res.json();
  },
};

// Minimal fetch wrapper with CSRF handling. CSP-safe (external file, no inline).
const API = {
  csrf: null,
  async _req(method, path, body, raw = false) {
    const opts = { method, headers: {}, credentials: "same-origin" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    if (method !== "GET" && this.csrf) opts.headers["X-CSRF-Token"] = this.csrf;
    const resp = await fetch("/api" + path, opts);
    if (raw) return resp;
    const data = resp.status === 204 ? null : await resp.json().catch(() => null);
    if (!resp.ok) {
      const err = new Error((data && data.detail) || resp.statusText);
      err.status = resp.status;
      err.code = data && data.code;
      throw err;
    }
    return data;
  },
  get(p) { return this._req("GET", p); },
  post(p, b) { return this._req("POST", p, b); },
  put(p, b) { return this._req("PUT", p, b); },
  del(p, b) { return this._req("DELETE", p, b); },
  async text(path) {
    const resp = await this._req("GET", path, undefined, true);
    return resp.text();
  },
};

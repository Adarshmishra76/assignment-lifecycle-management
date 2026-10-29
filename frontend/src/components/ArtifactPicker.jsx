import { useState } from "react";
import { sha256File } from "../lib/hash";
import { bytes } from "../lib/format";
import { Notice } from "./ui";

/** Builds the artifact metadata the API expects. The backend stores metadata only; file contents are hashed in the browser, not uploaded. */
export default function ArtifactPicker({ value, onChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const add = async (files) => {
    setBusy(true); setError(null);
    try {
      const added = [];
      for (const f of Array.from(files)) {
        added.push({ filename: f.name, mime_type: f.type || "application/octet-stream", file_size_bytes: f.size, checksum_sha256: await sha256File(f), availability_status: "available" });
      }
      onChange([...value, ...added]);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-3">
      <label className="block cursor-pointer rounded-md border-2 border-dashed border-ink-300 p-5 text-center text-sm text-ink-500 hover:border-brand-500">
        {busy ? "Computing checksums…" : "Choose files to attach"}
        <input type="file" multiple className="sr-only" disabled={busy} onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      </label>
      <p className="text-xs text-ink-500">File names, sizes and SHA-256 checksums are recorded. This backend stores artifact metadata, not file contents.</p>
      <Notice>{error}</Notice>
      {value.length > 0 && (
        <ul className="divide-y divide-paper-200 rounded-md border border-paper-200 text-sm">
          {value.map((a, i) => (
            <li key={`${a.checksum_sha256}-${i}`} className="flex items-center justify-between gap-3 px-3 py-2">
              <div className="min-w-0"><p className="truncate font-medium">{a.filename}</p><p className="truncate font-mono text-xs text-ink-500">{bytes(a.file_size_bytes)} · {a.checksum_sha256.slice(0, 16)}…</p></div>
              <button type="button" className="text-mark-500 hover:underline" onClick={() => onChange(value.filter((_, j) => j !== i))}>Remove</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

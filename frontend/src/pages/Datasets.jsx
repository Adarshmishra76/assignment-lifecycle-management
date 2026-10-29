import { useState } from "react";
import { datasetsApi } from "../api/endpoints";
import { download } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Card, ConfirmModal, DataTable, Field, Notice, PageHeader } from "../components/ui";
import { useToast } from "../components/Toast";
import { useApi } from "../hooks/useApi";
import { useLookups } from "../hooks/useLookups";
import { bytes, label } from "../lib/format";

function GenerateCard({ onDone }) {
  const toast = useToast();
  const lookups = useLookups();
  const [form, setForm] = useState({ mode: "starter", seed: "20261022", force: false, export: true });
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const run = async () => {
    setConfirm(false); setBusy(true); setError(null);
    try {
      setResult(await datasetsApi.generate({ mode: form.mode, seed: Number(form.seed), force: form.force, export: form.export }));
      toast.success("Dataset generated"); lookups.refresh(); onDone();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <Card title="Generate synthetic dataset">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2"><Notice>{error}</Notice></div>
        <Field label="Mode" hint={form.mode === "full" ? "10,000 learners and 30,000 submissions. This can take a while." : "20 learners and about 40 submissions."}><select className="input" value={form.mode} onChange={set("mode")}><option>starter</option><option>full</option></select></Field>
        <Field label="Seed" hint="The same seed produces the same data"><input type="number" className="input" value={form.seed} onChange={set("seed")} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.export} onChange={set("export")} /> Export CSV and JSON files</label>
        <label className="flex items-center gap-2 text-sm text-mark-700"><input type="checkbox" checked={form.force} onChange={set("force")} /> Force: replace existing data</label>
      </div>
      <button className="btn-primary mt-4" disabled={busy} onClick={() => (form.force || form.mode === "full" ? setConfirm(true) : run())}>{busy ? "Generating…" : "Generate"}</button>
      {result && (
        <div className="mt-5">
          <h3 className="mb-2 text-sm font-medium text-ink-500">Rows created ({result.mode}, seed {result.seed})</h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">{Object.entries(result.counts).map(([k, v]) => <div key={k} className="rounded-md bg-paper-100 px-3 py-2 text-sm"><span className="text-ink-500">{label(k)}</span><b className="float-right tabular-nums">{v}</b></div>)}</div>
        </div>
      )}
      {confirm && (
        <ConfirmModal title="Generate dataset?" danger={form.force} confirmLabel="Generate" onClose={() => setConfirm(false)} onConfirm={run}>
          {form.force && <p>This <b>deletes all existing data, including user accounts,</b> and replaces it with demo data. You may be signed out afterwards.</p>}
          {form.mode === "full" && <p>Full mode creates about 10,000 learners and 30,000 submissions and may take several minutes.</p>}
        </ConfirmModal>
      )}
    </Card>
  );
}

export default function Datasets() {
  const { role } = useAuth();
  const toast = useToast();
  const exportsQ = useApi(() => datasetsApi.exports(), []);
  const [downloading, setDownloading] = useState(null);
  const get = async (f) => {
    setDownloading(f.mode + f.filename);
    try { await download(datasetsApi.exportPath(f.mode, f.filename), f.filename); } catch (e) { toast.error(e.message); } finally { setDownloading(null); }
  };
  return (
    <>
      <PageHeader title="Datasets & export" subtitle="Generate reproducible synthetic data and download the exported files." />
      <div className="space-y-4">
        {can.generateDataset(role) && <GenerateCard onDone={exportsQ.reload} />}
        <Card title="Export files" padded={false} actions={<button className="btn-quiet btn-sm" onClick={exportsQ.reload}>Refresh</button>}>
          <DataTable rows={exportsQ.data?.files} rowKey="filename" loading={exportsQ.loading} error={exportsQ.error} onRetry={exportsQ.reload}
            emptyTitle="No exports yet" emptyText={can.generateDataset(role) ? "Generate a dataset with export enabled to create CSV and JSON files." : "Ask a platform administrator to generate an export."}
            columns={[{ header: "Mode", key: "mode" }, { header: "File", render: (f) => <code className="text-xs">{f.filename}</code> }, { header: "Size", render: (f) => bytes(f.size_bytes) },
              { header: "", render: (f) => <button className="btn-quiet btn-sm" disabled={downloading === f.mode + f.filename} onClick={() => get(f)}>{downloading === f.mode + f.filename ? "Downloading…" : "Download"}</button> }]} />
        </Card>
      </div>
    </>
  );
}

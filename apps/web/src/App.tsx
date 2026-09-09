/**
 * The December screen, in its October form.
 *
 * Left: the brief. Centre: the proposal image. Right: the same facade redrawn
 * as catalogue parts. Below: the three files a fabricator consumes.
 *
 * Everything that is a stub says so on screen. A demo that looks finished when
 * the legaliser is a baseline would mislead the person watching it.
 */

import { useEffect, useMemo, useState } from "react";
import {
  type CatalogueInfo,
  type Job,
  fileUrl,
  getCatalogues,
  getMasks,
  pollJob,
  submitJob,
} from "./api";

const EXAMPLE_BRIEFS = [
  "a six-storey office facade, deep reveals, horizontal banding",
  "a residential block, irregular window rhythm, warm cladding",
  "a civic building, tall ground floor, regular grid above",
];

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="metric">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      {hint && <div className="metric-hint">{hint}</div>}
    </div>
  );
}

export default function App() {
  const [brief, setBrief] = useState(EXAMPLE_BRIEFS[0]);
  const [catalogues, setCatalogues] = useState<CatalogueInfo[]>([]);
  const [catalogue, setCatalogue] = useState<string>("");
  const [masks, setMasks] = useState<string[]>([]);
  const [mask, setMask] = useState<string>("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCatalogues()
      .then((r) => {
        setCatalogues(r.catalogues);
        setCatalogue(r.default);
      })
      .catch((e) => setError(`cannot reach the API: ${e.message}`));
    getMasks()
      .then((r) => setMasks(r.masks))
      .catch(() => undefined);
  }, []);

  const running = job?.status === "queued" || job?.status === "running";

  async function run() {
    setBusy(true);
    setError(null);
    setJob(null);
    try {
      const submitted = await submitJob({
        brief,
        catalogue: catalogue || undefined,
        mask: mask || undefined,
      });
      setJob(submitted);
      await pollJob(submitted.id, setJob);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const m = job?.metrics ?? {};
  const pct = (v?: number) => (v === undefined ? "--" : `${Math.round(v * 100)}%`);
  const num = (v?: number, digits = 0) => (v === undefined ? "--" : v.toFixed(digits));

  const activeCatalogue = useMemo(
    () => catalogues.find((c) => c.file === catalogue),
    [catalogues, catalogue],
  );

  return (
    <main>
      <header>
        <div className="eyebrow">MaCAD thesis · Charles Abi Chahine · tutor Gabriella Rossi</div>
        <h1>FacadeKit</h1>
        <p className="lede">
          A brief becomes a facade image. The image is cut into panels. A solver forces those
          panels onto a real manufacturer&rsquo;s catalogue. The output is a panel schedule, a
          nesting layout and cut files &mdash; not a render.
        </p>
        <div className="banner">
          <strong>Skeleton, October 2026.</strong> The legaliser is the{" "}
          <em>baseline</em>: it gives each panel the nearest catalogue part by size, with no
          joint, adjacency, waste or part-count reasoning. The CP-SAT solver &mdash; the thesis
          &mdash; is not written yet. Nesting is naive shelf packing. Images are placeholders,
          not FLUX output.
        </div>
      </header>

      <section className="controls">
        <label className="field">
          <span>Brief</span>
          <textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={3}
            placeholder="a six-storey office facade, deep reveals"
          />
          <div className="examples">
            {EXAMPLE_BRIEFS.map((b) => (
              <button key={b} type="button" className="chip" onClick={() => setBrief(b)}>
                {b.split(",")[0]}
              </button>
            ))}
          </div>
        </label>

        <div className="field-row">
          <label className="field">
            <span>Catalogue</span>
            <select value={catalogue} onChange={(e) => setCatalogue(e.target.value)}>
              {catalogues.map((c) => (
                <option key={c.file} value={c.file} disabled={!c.ok}>
                  {c.system ?? c.file} {c.parts ? `(${c.parts} parts)` : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>
              Mask <small>optional &mdash; skips generation</small>
            </span>
            <select value={mask} onChange={(e) => setMask(e.target.value)}>
              <option value="">generate from the brief</option>
              {masks.map((f) => (
                <option key={f} value={f}>
                  {f.replace(".png", "")}
                </option>
              ))}
            </select>
          </label>

          <button className="primary" onClick={run} disabled={busy}>
            {running ? "Legalising…" : "Legalise"}
          </button>
        </div>
      </section>

      {error && <div className="error">{error}</div>}
      {job?.status === "error" && (
        <div className="error">
          <strong>Job failed.</strong> {job.error}
        </div>
      )}

      {running && <div className="status">Job {job?.id} is {job?.status}&hellip;</div>}

      {job?.status === "done" && (
        <>
          <section className="panels">
            <figure>
              <figcaption>
                Proposal <span className="tag">placeholder</span>
              </figcaption>
              {job.files.includes("proposal.png") ? (
                <img src={fileUrl(job.id, "proposal.png")} alt="Generated facade proposal" />
              ) : (
                <div className="empty">segmented directly from a mask &mdash; no image</div>
              )}
            </figure>

            <figure>
              <figcaption>
                Legalised <span className="tag tag-build">catalogue parts</span>
              </figcaption>
              <img src={fileUrl(job.id, "panel-map.png")} alt="Legalised panel map" />
            </figure>
          </section>

          <section className="metrics">
            <Metric
              label="legalised"
              value={pct(m.legalised_fraction)}
              hint={`${num(m.legalised)} of ${num(m.panels)} panels`}
            />
            <Metric label="unique parts" value={num(m.unique_parts)} hint="SKUs to order" />
            <Metric
              label="max fit error"
              value={`${num(m.max_fit_error_mm)} mm`}
              hint={`mean ${num(m.mean_fit_error_mm)} mm`}
            />
            <Metric
              label="sheet waste"
              value={`${num(m.waste_pct, 1)}%`}
              hint={`${num(m.sheets)} sheets, naive packing`}
            />
          </section>

          {job.warnings.length > 0 && (
            <ul className="warnings">
              {job.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}

          <section className="downloads">
            <a className="download" href={fileUrl(job.id, "schedule.csv")} download>
              <strong>Panel schedule</strong>
              <span>CSV &mdash; one row per panel</span>
            </a>
            <a className="download" href={fileUrl(job.id, "nesting.dxf")} download>
              <strong>Cut files</strong>
              <span>DXF &mdash; sheets and elevation</span>
            </a>
            <a className="download" href={fileUrl(job.id, "panel-map.png")} download>
              <strong>Panel map</strong>
              <span>PNG &mdash; labelled elevation</span>
            </a>
          </section>

          <footer className="run-meta">
            job {job.id} · {job.method} · generator {job.generator} ·{" "}
            {activeCatalogue?.system ?? catalogue} · solved in{" "}
            {num(m.solve_time_s !== undefined ? m.solve_time_s * 1000 : undefined)} ms
          </footer>
        </>
      )}
    </main>
  );
}

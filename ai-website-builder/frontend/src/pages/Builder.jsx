import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api/client";
import AgentPipeline from "../components/AgentPipeline";
import PreviewPane from "../components/PreviewPane";
import FileExplorer from "../components/FileExplorer";
import "./Builder.css";

const MODIFY_STEPS = [
  { key: "plan", label: "Change Planner" },
  { key: "modify", label: "Code Modification" },
  { key: "testing", label: "Testing" },
  { key: "debugging", label: "Debugging" },
];

const EXAMPLES = [
  "A modern portfolio for a software developer named Alex, dark theme, blue accents.",
  "A landing page for a SaaS product called Nimbus that schedules meetings across time zones.",
  "A restaurant website for 'Tide & Thyme', a modern seafood bistro, warm and elegant.",
];

function StatCard({ title, value }) {
  return (
    <div className="stat-card">
      <div className="stat-title">{title}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export default function Builder() {
  const location = useLocation();
  const [projectId, setProjectId] = useState(null);
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState(0.7);

  const [prompt, setPrompt] = useState(() => location.state?.prompt || "");
  const [websiteType, setWebsiteType] = useState("");
  const [visualStyle, setVisualStyle] = useState("");
  const [colors, setColors] = useState("");
  const [audience, setAudience] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("generate"); // "generate" | "modify"
  const [pipelineStatuses, setPipelineStatuses] = useState({});
  const [summary, setSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  const [activeTab, setActiveTab] = useState("preview");
  const [previewHtml, setPreviewHtml] = useState("");
  const [fileTree, setFileTree] = useState(null);
  const [selectedPath, setSelectedPath] = useState(null);
  const [selectedContent, setSelectedContent] = useState("");
  const [selectedLanguage, setSelectedLanguage] = useState(null);

  const [modifyText, setModifyText] = useState("");

  const unsubscribeRef = useRef(null);

  useEffect(() => {
    api.createProject().then((res) => setProjectId(res.project_id));
    api.listProviders().then((res) => {
      setProviders(res.providers);
      const first = res.providers.find((p) => p.id === "mock") || res.providers[0];
      if (first) {
        setProvider(first.id);
        setModel(first.models[0] || "");
      }
    });
    return () => unsubscribeRef.current?.();
  }, []);

  function onProviderChange(nextId) {
    setProvider(nextId);
    const found = providers.find((p) => p.id === nextId);
    setModel(found?.models[0] || "");
  }

  async function refreshResults(pid) {
    const [prev, tree] = await Promise.all([api.preview(pid), api.files(pid)]);
    setPreviewHtml(prev.html);
    setFileTree(tree);
    setSelectedPath(null);
    setSelectedContent("");
  }

  function subscribe(pid, steps) {
    unsubscribeRef.current?.();
    setPipelineStatuses(Object.fromEntries(steps.map((s) => [s.key, "pending"])));
    const unsubscribe = api.subscribeEvents(pid, {
      onEvent: async (event) => {
        if (event.type === "progress") {
          setPipelineStatuses((prev) => ({ ...prev, [event.step]: event.status }));
        } else if (event.type === "done") {
          setSummary(event.summary);
          if (event.summary?.status === "failed" && event.summary.errors?.length) {
            setErrorMessage(event.summary.errors.join("\n"));
          }
          setBusy(false);
          unsubscribe();
          try {
            await refreshResults(pid);
          } catch {
            /* preview/files best-effort */
          }
        } else if (event.type === "error") {
          setErrorMessage(event.message);
          setBusy(false);
          unsubscribe();
        }
      },
      onError: () => {
        // Connection hiccup — fall back to a short polling loop rather than
        // leaving the UI stuck mid-generation.
        unsubscribe();
        pollUntilDone(pid);
      },
    });
    unsubscribeRef.current = unsubscribe;
  }

  async function pollUntilDone(pid) {
    for (let i = 0; i < 200; i += 1) {
      const s = await api.status(pid).catch(() => null);
      if (!s) break;
      if (!s.busy) {
        setSummary(s);
        setBusy(false);
        try {
          await refreshResults(pid);
        } catch {
          /* best effort */
        }
        return;
      }
      await new Promise((r) => setTimeout(r, 700));
    }
    setBusy(false);
  }

  async function handleGenerate() {
    if (!projectId || !prompt.trim() || busy) return;
    setErrorMessage("");
    setMode("generate");
    setBusy(true);
    subscribe(projectId, [
      { key: "requirements", label: "Requirements" },
      { key: "ui_ux", label: "UI/UX" },
      { key: "architecture", label: "Architecture" },
      { key: "content", label: "Content" },
      { key: "code_gen", label: "Code" },
      { key: "testing", label: "Testing" },
      { key: "debugging", label: "Debugging" },
      { key: "quality", label: "Quality" },
    ]);
    try {
      await api.generate(projectId, {
        prompt,
        provider,
        model,
        temperature,
        website_type: websiteType || undefined,
        visual_style: visualStyle || undefined,
        colors: colors || undefined,
        audience: audience || undefined,
      });
    } catch (e) {
      setErrorMessage(e.message);
      setBusy(false);
      unsubscribeRef.current?.();
    }
  }

  async function handleModify() {
    if (!projectId || !modifyText.trim() || busy || !summary) return;
    setErrorMessage("");
    setMode("modify");
    setBusy(true);
    subscribe(projectId, MODIFY_STEPS);
    try {
      await api.modify(projectId, { request: modifyText, provider, model, temperature });
      setModifyText("");
    } catch (e) {
      setErrorMessage(e.message);
      setBusy(false);
      unsubscribeRef.current?.();
    }
  }

  async function handleStop() {
    if (!projectId) return;
    await api.cancel(projectId).catch(() => {});
  }

  async function handleReset() {
    if (!projectId) return;
    unsubscribeRef.current?.();
    await api.reset(projectId).catch(() => {});
    const res = await api.createProject();
    setProjectId(res.project_id);
    setPrompt("");
    setWebsiteType("");
    setVisualStyle("");
    setColors("");
    setAudience("");
    setModifyText("");
    setSummary(null);
    setPipelineStatuses({});
    setPreviewHtml("");
    setFileTree(null);
    setSelectedPath(null);
    setSelectedContent("");
    setErrorMessage("");
    setBusy(false);
  }

  async function selectFile(path) {
    if (!projectId) return;
    setSelectedPath(path);
    const res = await api.fileContent(projectId, path);
    setSelectedContent(res.content);
    setSelectedLanguage(res.language);
  }

  const hasResult = Boolean(summary && summary.files_count > 0);
  const steps = mode === "modify" ? MODIFY_STEPS : undefined;

  return (
    <div className="builder">
      <div className="builder-topbar">
        <div className="builder-topbar-inner container">
          <span className="builder-title">Builder</span>
          <button type="button" className="btn" onClick={handleReset}>New Project</button>
        </div>
      </div>

      <div className="builder-grid container">
        {/* LEFT — configuration */}
        <aside className="panel builder-left">
          <h3 className="panel-heading">Describe your website</h3>
          <textarea
            className="field textarea"
            placeholder="Create a modern portfolio website for a software developer..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={6}
          />
          <div className="examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="example-pill" onClick={() => setPrompt(ex)}>
                {ex.length > 46 ? `${ex.slice(0, 46)}…` : ex}
              </button>
            ))}
          </div>

          <div className="field-row">
            <label className="field-label">
              Website type
              <input className="field" value={websiteType} onChange={(e) => setWebsiteType(e.target.value)}
                     placeholder="Portfolio, SaaS, restaurant…" />
            </label>
            <label className="field-label">
              Visual style
              <input className="field" value={visualStyle} onChange={(e) => setVisualStyle(e.target.value)}
                     placeholder="Minimal, bold, playful…" />
            </label>
          </div>
          <div className="field-row">
            <label className="field-label">
              Preferred colors
              <input className="field" value={colors} onChange={(e) => setColors(e.target.value)}
                     placeholder="Navy and gold" />
            </label>
            <label className="field-label">
              Target audience
              <input className="field" value={audience} onChange={(e) => setAudience(e.target.value)}
                     placeholder="Freelance clients" />
            </label>
          </div>

          <h3 className="panel-heading">LLM configuration</h3>
          <div className="field-row">
            <label className="field-label">
              Provider
              <select className="field" value={provider} onChange={(e) => onProviderChange(e.target.value)}>
                {providers.map((p) => (
                  <option key={p.id} value={p.id} disabled={p.requires_api_key && !p.configured}>
                    {p.label}{p.requires_api_key && !p.configured ? " (no API key)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Model
              <select className="field" value={model} onChange={(e) => setModel(e.target.value)}>
                {(providers.find((p) => p.id === provider)?.models || []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
          </div>

          <button type="button" className="advanced-toggle" onClick={() => setAdvancedOpen((o) => !o)}>
            Advanced settings {advancedOpen ? "▾" : "▸"}
          </button>
          {advancedOpen && (
            <label className="field-label">
              Temperature: {temperature.toFixed(2)}
              <input
                type="range" min="0" max="1" step="0.05" value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
              />
            </label>
          )}

          {errorMessage && <div className="error-box">{errorMessage}</div>}

          <div className="builder-cta-row">
            <button type="button" className="btn btn-primary" onClick={handleGenerate} disabled={busy || !prompt.trim()}>
              {busy && mode === "generate" ? "Generating…" : "Generate Website"}
            </button>
            {busy && <button type="button" className="btn" onClick={handleStop}>Stop</button>}
          </div>
        </aside>

        {/* CENTER — preview / files */}
        <main className="builder-center">
          <div className="tab-bar">
            <button className={activeTab === "preview" ? "active" : ""} onClick={() => setActiveTab("preview")}>Preview</button>
            <button className={activeTab === "files" ? "active" : ""} onClick={() => setActiveTab("files")}>Files</button>
          </div>
          <div className="tab-body">
            {activeTab === "preview" ? (
              <PreviewPane
                html={previewHtml}
                empty={!hasResult}
                onRefresh={() => projectId && refreshResults(projectId)}
                onExport={() => projectId && window.open(api.exportUrl(projectId), "_blank")}
              />
            ) : (
              <FileExplorer
                tree={fileTree}
                empty={!hasResult}
                selectedPath={selectedPath}
                content={selectedContent}
                language={selectedLanguage}
                onSelect={selectFile}
              />
            )}
          </div>
        </main>

        {/* RIGHT — agent activity + dashboard + modify */}
        <aside className="panel builder-right">
          <h3 className="panel-heading">Agent activity</h3>
          <AgentPipeline statuses={pipelineStatuses} steps={steps} />

          <h3 className="panel-heading">Project dashboard</h3>
          {summary && summary.status !== "idle" ? (
            <div className="stat-grid">
              <StatCard title="Status" value={summary.status} />
              <StatCard title="Quality" value={summary.quality_score != null ? `${summary.quality_score}/100` : "—"} />
              <StatCard title="Files" value={summary.files_count ?? "—"} />
              <StatCard
                title="Tests"
                value={summary.tests_passed == null ? "—" : summary.tests_passed ? "Passed" : `${summary.test_errors?.length || 0} issue(s)`}
              />
              <StatCard title="Debug iterations" value={summary.debug_iterations ?? 0} />
              <StatCard title="Elapsed" value={summary.elapsed_seconds != null ? `${summary.elapsed_seconds.toFixed(1)}s` : "—"} />
            </div>
          ) : (
            <div className="dashboard-empty">Generate a website to see project stats.</div>
          )}

          <h3 className="panel-heading">What would you like to change?</h3>
          <textarea
            className="field textarea"
            placeholder="Make the hero section darker. Add a pricing section…"
            value={modifyText}
            onChange={(e) => setModifyText(e.target.value)}
            rows={3}
            disabled={!hasResult}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleModify}
            disabled={busy || !hasResult || !modifyText.trim()}
          >
            {busy && mode === "modify" ? "Refining…" : "Refine Website"}
          </button>
        </aside>
      </div>
    </div>
  );
}

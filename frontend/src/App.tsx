import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  Cpu,
  Database,
  FlaskConical,
  FolderOpen,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Menu,
  MessageSquare,
  PanelLeftClose,
  Plus,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import { Field } from "./components/Field";
import {
  newProject,
  sections,
  type Project,
  type Source,
} from "./types/project";
import { readiness, validate } from "./features/project-setup/validation";
import { listProjects, loadProject, saveProject } from "./services/projects";
import { loadProject as loadLegacyProject } from "./services/legacy-project";
import { Environment } from "./components/Environment";
const nav: { name: string; icon: LucideIcon }[] = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Project Setup", icon: Settings2 },
  { name: "Environment", icon: Terminal },
  { name: "Datasets", icon: Database },
  { name: "Tokenizer", icon: ListChecks },
  { name: "Model Config", icon: Cpu },
  { name: "Pre-training", icon: FlaskConical },
  { name: "Evaluation", icon: Gauge },
  { name: "Fine-tuning", icon: Sparkles },
  { name: "Playground", icon: MessageSquare },
];
const taskNames = {
  completion: "Text completion",
  chatbot: "Chatbot",
  "domain-assistant": "Domain assistant",
};
const languageNames = {
  bn: "Bangla",
  en: "English",
  mixed: "Bangla + English",
};
const routeFor = (name: string) =>
  `#/${name.toLowerCase().replaceAll(" ", "-")}`;
const pageFromHash = () =>
  nav.find((item) => routeFor(item.name) === window.location.hash)?.name ??
  "Overview";
export default function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [savedJson, setSavedJson] = useState("null");
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [legacy, setLegacy] = useState<Project | null>(null);
  const [connected, setConnected] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [page, setPage] = useState(pageFromHash);
  const [section, setSection] = useState(0);
  const [menu, setMenu] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const loadSequence = useRef(0);
  const dirty = JSON.stringify(project) !== savedJson;
  async function refreshProjects() {
    const sequence = ++loadSequence.current;
    setLoading(true);
    setError("");
    try {
      const all = await listProjects();
      if (sequence !== loadSequence.current) return;
      setProjects(all);
      setConnected(true);
      const current = all[0] ?? null;
      setProject(current);
      setSavedJson(JSON.stringify(current));
    } catch (e) {
      if (sequence !== loadSequence.current) return;
      setConnected(false);
      setError(
        `Could not load PostgreSQL projects. ${e instanceof Error ? e.message : "Check the backend and database."}`,
      );
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }
  useEffect(() => {
    void refreshProjects();
    try {
      setLegacy(loadLegacyProject(window.localStorage));
    } catch {
      setNotice(
        "A previous browser draft could not be read. It has been left untouched.",
      );
    }
  }, []);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  useEffect(() => {
    if (!pending) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const first = document.querySelector<HTMLButtonElement>(
      '[role="dialog"] button',
    );
    first?.focus();
    const trap = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPending(null);
      if (e.key !== "Tab") return;
      const buttons = Array.from(
        document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button'),
      );
      const target = e.shiftKey ? buttons.at(-1) : buttons[0];
      if (
        (e.shiftKey && document.activeElement === buttons[0]) ||
        (!e.shiftKey && document.activeElement === buttons.at(-1))
      ) {
        e.preventDefault();
        target?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      previousFocus?.focus();
    };
  }, [pending]);
  useEffect(() => {
    window.history.replaceState(null, "", routeFor(page));
    const onRoute = () => {
      const target = pageFromHash();
      if (target === page) return;
      if (dirty) {
        window.history.replaceState(null, "", routeFor(page));
        setPending(target);
      } else setPage(target);
    };
    window.addEventListener("hashchange", onRoute);
    return () => window.removeEventListener("hashchange", onRoute);
  }, [page, dirty]);
  useEffect(() => {
    if (!menu) return;
    const previous = document.activeElement as HTMLElement | null;
    const controls = () =>
      Array.from(
        document.querySelectorAll<HTMLElement>(".sidebar a, .sidebar button"),
      );
    controls()[0]?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenu(false);
      if (e.key === "Tab") {
        const items = controls();
        if (e.shiftKey && document.activeElement === items[0]) {
          e.preventDefault();
          items.at(-1)?.focus();
        }
        if (!e.shiftKey && document.activeElement === items.at(-1)) {
          e.preventDefault();
          items[0]?.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [menu]);
  const p = project;
  const state = p ? readiness(p) : null;
  const issues = p ? validate(p) : [];
  function update(patch: Partial<Project>) {
    if (p) {
      setProject({ ...p, ...patch, status: "draft" });
      setNotice("");
    }
  }
  function navigate(next: string) {
    if (saving) return;
    setMenu(false);
    if (next === page) return;
    if (dirty) setPending(next);
    else setPage(next);
  }
  async function applyNavigation(next: string) {
    if (next === "new-project") {
      start();
      return;
    }
    if (next.startsWith("project:")) {
      setLoading(true);
      setError("");
      try {
        const loaded = await loadProject(next.slice(8));
        setProject(loaded);
        setSavedJson(JSON.stringify(loaded));
        setPage("Overview");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load project.");
      } finally {
        setLoading(false);
      }
      return;
    }
    setPage(next);
  }
  function chooseProject(next: string) {
    if (saving) return;
    if (dirty) setPending(next);
    else void applyNavigation(next);
  }
  function start() {
    setError("");
    setProject(newProject());
    setSection(0);
    setPage("Project Setup");
    setNotice("");
  }
  async function save(ready = false) {
    if (!p || saving) return false;
    setSaving(true);
    setNotice("");
    setError("");
    try {
      const saved = await saveProject({
        ...p,
        status: ready ? "scope-ready" : p.status,
      });
      setProject(saved);
      setConnected(true);
      setProjects((current) => [
        saved,
        ...current.filter((item) => item.id !== saved.id),
      ]);
      setSavedJson(JSON.stringify(saved));
      setNotice(
        ready
          ? "Scope marked ready. Environment verification is next."
          : "Draft saved to PostgreSQL.",
      );
      return true;
    } catch (e) {
      if (
        e instanceof Error &&
        /PostgreSQL is unavailable|Cannot reach the Python server/.test(
          e.message,
        )
      )
        setConnected(false);
      setError(
        `Could not save your draft. ${e instanceof Error ? e.message : "Check the Python server and PostgreSQL service."} Your edits are still open.`,
      );
      return false;
    } finally {
      setSaving(false);
    }
  }
  const hardware = (patch: Partial<Project["hardware"]>) =>
    p && update({ hardware: { ...p.hardware, ...patch } });
  const budget = (patch: Partial<Project["budget"]>) =>
    p && update({ budget: { ...p.budget, ...patch } });
  const criteria = (patch: Partial<Project["successCriteria"]>) =>
    p && update({ successCriteria: { ...p.successCriteria, ...patch } });
  const source = (id: string, patch: Partial<Source>) =>
    p &&
    update({
      sources: p.sources.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    });
  const text = (
    label: string,
    value: string,
    change: (v: string) => void,
    placeholder = "",
    multiline = false,
  ) => (
    <Field label={label}>
      {(id) =>
        multiline ? (
          <textarea
            id={id}
            value={value}
            onChange={(e) => change(e.target.value)}
            placeholder={placeholder}
            rows={3}
          />
        ) : (
          <input
            id={id}
            value={value}
            onChange={(e) => change(e.target.value)}
            placeholder={placeholder}
          />
        )
      }
    </Field>
  );
  const numeric = (
    label: string,
    value: number | null,
    change: (v: number | null) => void,
    field: string,
    zero = false,
    integer = false,
  ) => {
    const issue = issues.find((i) => i.field === field);
    return (
      <Field label={label}>
        {(id) => (
          <>
            <input
              id={id}
              type="number"
              min={zero ? 0 : integer ? 1 : 0.01}
              step={integer ? 1 : "any"}
              value={value ?? ""}
              onChange={(e) =>
                change(e.target.value === "" ? null : e.target.valueAsNumber)
              }
              placeholder="Not set"
              aria-invalid={!!issue}
              aria-describedby={issue ? `${id}-error` : undefined}
            />
            {issue && (
              <small className="field-error" id={`${id}-error`}>
                {issue.message}
              </small>
            )}
          </>
        )}
      </Field>
    );
  };
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to workspace
      </a>
      {menu && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <button
          className="icon-button close-menu"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        >
          <X size={18} />
        </button>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("Overview");
          }}
        >
          <span className="brand-mark">
            <FlaskConical size={21} />
          </span>
          <span>
            Pre-training<span className="brand-sub">STUDIO</span>
          </span>
        </a>
        <div className="workspace-label">
          WORKSPACE <span>LOCAL</span>
        </div>
        <div className="workspace-card">
          <span className="project-icon">
            <FolderOpen size={18} />
          </span>
          <div>
            <strong>{p?.name || "Your first model"}</strong>
            <small>{p ? "Personal workspace" : "Start something new"}</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <div className="nav-label">BUILD YOUR MODEL</div>
        <nav aria-label="Main navigation">
          {nav.map(({ name, icon: Icon }, index) => (
            <button
              key={name}
              className={`nav-item ${page === name ? "active" : ""}`}
              aria-current={page === name ? "page" : undefined}
              onClick={() => navigate(name)}
            >
              <Icon size={18} />
              <span>{name}</span>
              {index > 2 && <span className="nav-planned">Soon</span>}
              {page === name && <span className="active-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <span className="status-dot" />
            <span>
              Local workspace<small>Your ideas start here.</small>
            </span>
          </div>
          <div className="sidebar-footer">
            <span>PRE-TRAINING STUDIO</span>
            <span>v0.1</span>
          </div>
        </div>
      </aside>
      <div className="workspace" inert={!!pending || menu}>
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMenu(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb-home">Workspace</span>
            <ChevronRight size={14} />
            <strong>{page}</strong>
          </div>
          <div className="topbar-right">
            <span className="local-badge">
              <span className="status-dot" />{" "}
              {connected ? "PostgreSQL" : "Offline"}
            </span>
            <span className="avatar">ME</span>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          <div role="status" aria-live="polite">
            {notice && (
              <div className="notice">
                <Check size={16} />
                {notice}
                <button
                  aria-label="Dismiss notification"
                  onClick={() => setNotice("")}
                >
                  <X size={15} />
                </button>
              </div>
            )}
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          <div className="project-toolbar">
            <div
              className={`server-status ${connected ? "online" : "offline"}`}
            >
              <span className="status-dot" />
              {connected
                ? "PostgreSQL connected"
                : "Server connection unavailable"}
            </div>
            <label className="project-select">
              Project
              <select
                aria-label="Select saved project"
                disabled={saving || loading}
                value={p?.revision ? p.id : ""}
                onChange={(e) => {
                  if (e.target.value)
                    chooseProject(`project:${e.target.value}`);
                }}
              >
                <option value="">
                  {p && !p.revision ? "Unsaved project" : "Choose project"}
                </option>
                {projects.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name || "Untitled project"}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="secondary"
              disabled={saving || loading}
              onClick={() => chooseProject("new-project")}
            >
              <Plus size={14} />
              New project
            </button>
            {!connected && (
              <button
                className="secondary"
                disabled={loading || dirty}
                onClick={() => void refreshProjects()}
              >
                Retry connection
              </button>
            )}
          </div>
          {legacy && (
            <div className="legacy-banner">
              <div>
                <strong>
                  Previous browser draft found:{" "}
                  {legacy.name || "Untitled project"}
                </strong>
                <p>
                  Import a copy into a new project draft, then save it to
                  PostgreSQL. The browser copy will remain untouched.
                </p>
              </div>
              <button
                className="secondary"
                disabled={dirty || saving}
                onClick={() => {
                  setProject({
                    ...legacy,
                    id: crypto.randomUUID(),
                    revision: 0,
                    updatedAt: "",
                    status: "draft",
                  });
                  setSection(0);
                  setPage("Project Setup");
                  setLegacy(null);
                }}
              >
                Import browser draft
              </button>
              <button
                className="icon-button"
                aria-label="Dismiss browser draft import"
                onClick={() => setLegacy(null)}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="empty-card">Opening your workspace…</div>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">YOUR MODEL. FROM THE GROUND UP.</div>
                  <h1>
                    {page === "Overview"
                      ? "A small model. A big beginning."
                      : page === "Project Setup"
                        ? "Let’s lay the groundwork."
                        : page}
                  </h1>
                  <p>
                    {page === "Overview"
                      ? "Turn your first idea into a clear, reproducible training plan."
                      : page === "Project Setup"
                        ? "Define what you’re building, what you have, and what success looks like."
                        : page === "Environment"
                          ? "Verify your Python environment and inspect the resources on your backend host."
                          : "One step at a time. This part of your model journey is coming next."}
                  </p>
                </div>
                {page === "Overview" && p && (
                  <button
                    className="primary"
                    onClick={() => {
                      setSection(
                        state!.checks.findIndex((c) => !c.complete) < 0
                          ? 5
                          : state!.checks.findIndex((c) => !c.complete),
                      );
                      navigate("Project Setup");
                    }}
                  >
                    Continue setup
                    <ArrowRight size={16} />
                  </button>
                )}
              </div>
              {page === "Overview" ? (
                <>
                  <div className="overview-grid">
                    <section className="hero-card">
                      <div className="hero-copy">
                        <span className="pill">
                          <span className="status-dot" /> PHASE 00 · FOUNDATION
                        </span>
                        <h2>
                          {p
                            ? p.name || "Your project is taking shape."
                            : "Every great model starts\nwith a good plan."}
                        </h2>
                        <p>
                          {p
                            ? "Your workspace is ready to grow with you. Finish your scope before moving into environment setup."
                            : "Define your scope, map your resources, and give your first language model a thoughtful starting point."}
                        </p>
                        <button
                          className="primary"
                          onClick={() => {
                            if (!p) start();
                            else {
                              setSection(0);
                              navigate("Project Setup");
                            }
                          }}
                        >
                          {p
                            ? "Open project setup"
                            : "Create your first project"}
                          <ArrowRight size={17} />
                        </button>
                        <div className="hero-caption">
                          <ShieldCheck size={14} />
                          Stored in PostgreSQL. Built at your own pace.
                        </div>
                      </div>
                      <div className="model-art" aria-hidden="true">
                        <div className="orbit orbit-one" />
                        <div className="orbit orbit-two" />
                        <div className="orbit orbit-three" />
                        <span className="art-core">
                          <Cpu size={42} strokeWidth={1.2} />
                        </span>
                        <span className="art-node node-one" />
                        <span className="art-node node-two" />
                        <span className="art-node node-three" />
                      </div>
                    </section>
                    <section className="card readiness-card">
                      <div className="card-heading">
                        <h3>Scope readiness</h3>
                        <span className="muted">01 / 06</span>
                      </div>
                      <div className="progress-summary">
                        <strong>
                          {state?.percent ?? 0}
                          <span>%</span>
                        </strong>
                        <span>
                          {state?.ready
                            ? "Ready for the next step"
                            : "A little planning goes a long way"}
                        </span>
                      </div>
                      <div className="progress-track">
                        <div style={{ width: `${state?.percent ?? 0}%` }} />
                      </div>
                      <div className="mini-checklist">
                        {(
                          state?.checks ??
                          [
                            "Project scope",
                            "Hardware recorded",
                            "Budget defined",
                            "Data permissions",
                            "Success criteria",
                          ].map((title) => ({ title, complete: false }))
                        ).map((c) => (
                          <div key={c.title}>
                            {c.complete ? (
                              <Check size={15} className="green" />
                            ) : (
                              <Circle size={13} />
                            )}
                            <span>{c.title}</span>
                            {c.complete && <small>Done</small>}
                          </div>
                        ))}
                      </div>
                    </section>
                  </div>
                  <div className="section-heading">
                    <div>
                      <h2>Your training journey</h2>
                      <p>
                        A clear path from a blank canvas to your own language
                        model.
                      </p>
                    </div>
                    <span className="subtle-label">6 MILESTONES</span>
                  </div>
                  <div className="journey-grid">
                    {[
                      [
                        "01",
                        "Define the scope",
                        "Set your task, resources and success criteria.",
                        Settings2,
                      ],
                      [
                        "02",
                        "Prepare the data",
                        "Clean your sources and build a tokenizer.",
                        Database,
                      ],
                      [
                        "03",
                        "Verify the pipeline",
                        "Run a smoke test before the real thing.",
                        Terminal,
                      ],
                      [
                        "04",
                        "Pre-train the model",
                        "Learn language patterns from scratch.",
                        Cpu,
                      ],
                      [
                        "05",
                        "Fine-tune behavior",
                        "Teach your model to follow instructions.",
                        Sparkles,
                      ],
                      [
                        "06",
                        "Evaluate & use",
                        "Measure quality and bring it to life.",
                        MessageSquare,
                      ],
                    ].map(([num, title, detail, Icon], i) => {
                      const ItemIcon = Icon as LucideIcon;
                      return (
                        <button
                          className={`journey-card ${i === 0 ? "current" : ""}`}
                          key={String(num)}
                          onClick={() => {
                            if (i === 0) {
                              if (!p) start();
                              else navigate("Project Setup");
                            } else
                              navigate(
                                [
                                  "",
                                  "Datasets",
                                  "Environment",
                                  "Pre-training",
                                  "Fine-tuning",
                                  "Evaluation",
                                ][i],
                              );
                          }}
                        >
                          <div className="journey-top">
                            <span className="journey-icon">
                              <ItemIcon size={20} />
                            </span>
                            <span>{String(num)}</span>
                          </div>
                          <h3>{String(title)}</h3>
                          <p>{String(detail)}</p>
                          <div className="journey-status">
                            {i === 0 ? (
                              <>
                                <span className="status-dot" />
                                {state?.ready ? "Scope ready" : "Start here"}
                                <ArrowUpRight size={15} />
                              </>
                            ) : (
                              "Planned"
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  <div className="bottom-note">
                    <span>
                      <FlaskConical size={18} />
                      <strong>Small by design. Reproducible by default.</strong>
                    </span>
                    <p>
                      Start with a learning model. Scale when the evidence says
                      you’re ready.
                    </p>
                  </div>
                </>
              ) : page === "Project Setup" ? (
                !p ? (
                  <section className="empty-card">
                    <FolderOpen size={35} />
                    <h2>A fresh start for your model</h2>
                    <p>
                      Create a project to record your scope, resources and
                      goals.
                    </p>
                    <button className="primary" onClick={start}>
                      Create project
                      <Plus size={16} />
                    </button>
                  </section>
                ) : (
                  <>
                    <div className="setup-meta">
                      <span
                        className={`pill ${p.status === "scope-ready" ? "ready" : ""}`}
                      >
                        {p.status === "scope-ready" ? (
                          <Check size={13} />
                        ) : (
                          <span className="status-dot" />
                        )}
                        {p.status === "scope-ready"
                          ? "SCOPE READY"
                          : "PROJECT DRAFT"}
                      </span>
                      <span>
                        {dirty
                          ? "Unsaved changes"
                          : p.updatedAt
                            ? `Last saved ${new Date(p.updatedAt).toLocaleString()}`
                            : "Not saved yet"}
                      </span>
                      <span className="meta-progress">
                        {state!.percent}% complete
                      </span>
                    </div>
                    <div className="setup-layout">
                      <aside
                        className="setup-steps"
                        aria-label="Setup sections"
                      >
                        {sections.map((name, i) => (
                          <button
                            key={name}
                            className={section === i ? "selected" : ""}
                            onClick={() => setSection(i)}
                            aria-current={section === i ? "step" : undefined}
                          >
                            <span
                              className={`step-number ${state!.checks[i]?.complete ? "completed" : ""}`}
                            >
                              {state!.checks[i]?.complete ? (
                                <Check size={13} />
                              ) : (
                                `0${i + 1}`
                              )}
                            </span>
                            <span>{name}</span>
                            <ChevronRight size={14} />
                          </button>
                        ))}
                        <div className="setup-tip">
                          <ShieldCheck size={20} />
                          <strong>A plan, before a run.</strong>
                          <p>
                            Scope readiness records your requirements. Hardware
                            verification comes next.
                          </p>
                        </div>
                      </aside>
                      <section className="card setup-form">
                        <div className="form-heading">
                          <span className="eyebrow">
                            STEP 0{section + 1} / 06
                          </span>
                          <h2>
                            {
                              [
                                "Make it your own.",
                                "Know your resources.",
                                "Set your boundaries.",
                                "Start with good sources.",
                                "Define a good result.",
                                "Ready for the next step?",
                              ][section]
                            }
                          </h2>
                          <p>
                            {
                              [
                                "Give your experiment a name and a clear direction.",
                                "Record your hardware manually. We’ll verify it in the next phase.",
                                "Record your limits before committing to a training run.",
                                "Record source metadata and confirm permission to use it.",
                                "Describe how you’ll know the model is useful.",
                                "Review your requirements. You can save a partial draft at any time.",
                              ][section]
                            }
                          </p>
                        </div>
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            void save();
                          }}
                          noValidate
                        >
                          <fieldset
                            disabled={saving}
                            className="saving-fieldset"
                          >
                            {section === 0 && (
                              <div className="form-fields">
                                {text(
                                  "Project name",
                                  p.name,
                                  (v) => update({ name: v }),
                                  "e.g. Bangla Mini — first experiment",
                                )}
                                {text(
                                  "Description (optional)",
                                  p.description,
                                  (v) => update({ description: v }),
                                  "A little context for your future self…",
                                  true,
                                )}
                                <div className="field-grid">
                                  <Field label="Target task">
                                    {(id) => (
                                      <select
                                        id={id}
                                        value={p.task ?? ""}
                                        onChange={(e) =>
                                          update({
                                            task:
                                              (e.target
                                                .value as Project["task"]) ||
                                              null,
                                          })
                                        }
                                      >
                                        <option value="">Choose a task</option>
                                        {Object.entries(taskNames).map(
                                          ([v, name]) => (
                                            <option key={v} value={v}>
                                              {name}
                                            </option>
                                          ),
                                        )}
                                      </select>
                                    )}
                                  </Field>
                                  <Field label="Language">
                                    {(id) => (
                                      <select
                                        id={id}
                                        value={p.language ?? ""}
                                        onChange={(e) =>
                                          update({
                                            language:
                                              (e.target
                                                .value as Project["language"]) ||
                                              null,
                                          })
                                        }
                                      >
                                        <option value="">
                                          Choose a language
                                        </option>
                                        {Object.entries(languageNames).map(
                                          ([v, name]) => (
                                            <option key={v} value={v}>
                                              {name}
                                            </option>
                                          ),
                                        )}
                                      </select>
                                    )}
                                  </Field>
                                </div>
                                {text(
                                  "Primary objective",
                                  p.objective,
                                  (v) => update({ objective: v }),
                                  "e.g. Learn to train a small, reproducible Bangla chatbot.",
                                  true,
                                )}
                                <div className="info-note">
                                  <Sparkles size={17} />
                                  <span>
                                    Start small. Model architecture comes after
                                    hardware checks and a measured pilot run.
                                  </span>
                                </div>
                              </div>
                            )}
                            {section === 1 && (
                              <div className="form-fields">
                                <div className="field-grid">
                                  <Field label="Training location">
                                    {(id) => (
                                      <select
                                        id={id}
                                        value={p.hardware.location ?? ""}
                                        onChange={(e) =>
                                          hardware({
                                            location:
                                              (e.target
                                                .value as Project["hardware"]["location"]) ||
                                              null,
                                          })
                                        }
                                      >
                                        <option value="">
                                          Choose location
                                        </option>
                                        <option value="local">
                                          Local machine
                                        </option>
                                        <option value="cloud">Cloud GPU</option>
                                      </select>
                                    )}
                                  </Field>
                                  <Field label="Hardware information">
                                    {(id) => (
                                      <select
                                        id={id}
                                        value={p.hardware.status}
                                        onChange={(e) =>
                                          hardware({
                                            status: e.target.value as
                                              "unknown" | "entered",
                                          })
                                        }
                                      >
                                        <option value="unknown">
                                          Not checked yet
                                        </option>
                                        <option value="entered">
                                          Enter hardware manually
                                        </option>
                                      </select>
                                    )}
                                  </Field>
                                </div>
                                {p.hardware.status === "entered" ? (
                                  <>
                                    {text(
                                      "GPU model",
                                      p.hardware.gpuModel,
                                      (v) => hardware({ gpuModel: v }),
                                      "e.g. NVIDIA RTX 4090",
                                    )}
                                    <div className="field-grid">
                                      {numeric(
                                        "GPU count",
                                        p.hardware.gpuCount,
                                        (v) => hardware({ gpuCount: v }),
                                        "GPU count",
                                        false,
                                        true,
                                      )}
                                      {numeric(
                                        "VRAM per GPU (GB)",
                                        p.hardware.vramPerGpuGb,
                                        (v) => hardware({ vramPerGpuGb: v }),
                                        "VRAM",
                                      )}
                                      {numeric(
                                        "System RAM (GB)",
                                        p.hardware.ramGb,
                                        (v) => hardware({ ramGb: v }),
                                        "RAM",
                                      )}
                                      {numeric(
                                        "Free disk space (GB)",
                                        p.hardware.freeDiskGb,
                                        (v) => hardware({ freeDiskGb: v }),
                                        "Free disk",
                                      )}
                                    </div>
                                  </>
                                ) : (
                                  <div className="info-note">
                                    <Cpu size={20} />
                                    <span>
                                      No problem if you don’t know yet. Save
                                      your draft and come back once you’ve
                                      checked. Scope readiness requires recorded
                                      hardware.
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}
                            {section === 2 && (
                              <div className="form-fields">
                                <div className="field-grid">
                                  {numeric(
                                    "Maximum training time (hours)",
                                    p.budget.maxHours,
                                    (v) => budget({ maxHours: v }),
                                    "Training hours",
                                  )}
                                  {numeric(
                                    `Maximum cost (${p.budget.currency})${p.hardware.location !== "cloud" ? " · optional" : ""}`,
                                    p.budget.maxCost,
                                    (v) => budget({ maxCost: v }),
                                    "Maximum cost",
                                    true,
                                  )}
                                  <Field label="Currency">
                                    {(id) => (
                                      <select
                                        id={id}
                                        value={p.budget.currency}
                                        onChange={(e) =>
                                          budget({ currency: e.target.value })
                                        }
                                      >
                                        <option>USD</option>
                                        <option>BDT</option>
                                        <option>EUR</option>
                                        <option>GBP</option>
                                      </select>
                                    )}
                                  </Field>
                                </div>
                                <div className="info-note">
                                  <Gauge size={18} />
                                  <span>
                                    These are planning limits. Cost estimates
                                    and automatic budget enforcement will come
                                    with the training pipeline.
                                  </span>
                                </div>
                              </div>
                            )}
                            {section === 3 && (
                              <div className="form-fields">
                                <Field label="Do you already have training data?">
                                  {(id) => (
                                    <select
                                      id={id}
                                      value={
                                        p.hasExistingData === null
                                          ? ""
                                          : String(p.hasExistingData)
                                      }
                                      onChange={(e) =>
                                        update({
                                          hasExistingData:
                                            e.target.value === ""
                                              ? null
                                              : e.target.value === "true",
                                        })
                                      }
                                    >
                                      <option value="">Choose an answer</option>
                                      <option value="true">
                                        Yes — I have existing data
                                      </option>
                                      <option value="false">
                                        No — I’m planning my sources
                                      </option>
                                    </select>
                                  )}
                                </Field>
                                {p.sources.map((s, i) => (
                                  <div className="source-card" key={s.id}>
                                    <div className="card-heading">
                                      <h3>
                                        Source {String(i + 1).padStart(2, "0")}
                                      </h3>
                                      <button
                                        className="icon-button"
                                        type="button"
                                        aria-label={`Remove source ${i + 1}`}
                                        onClick={() =>
                                          update({
                                            sources: p.sources.filter(
                                              (item) => item.id !== s.id,
                                            ),
                                          })
                                        }
                                      >
                                        <Trash2 size={16} />
                                      </button>
                                    </div>
                                    {text(
                                      "Source name",
                                      s.name,
                                      (v) => source(s.id, { name: v }),
                                      "e.g. Licensed Bangla articles",
                                    )}
                                    {text(
                                      "URL or local path reference",
                                      s.reference,
                                      (v) => source(s.id, { reference: v }),
                                      "https://… or /path/to/data",
                                    )}
                                    <div className="field-grid">
                                      {text(
                                        "Source language",
                                        s.language,
                                        (v) => source(s.id, { language: v }),
                                        "e.g. Bangla",
                                      )}
                                      <Field label="Usage permission">
                                        {(id) => (
                                          <select
                                            id={id}
                                            value={s.permission}
                                            onChange={(e) =>
                                              source(s.id, {
                                                permission: e.target
                                                  .value as Source["permission"],
                                              })
                                            }
                                          >
                                            <option value="unknown">
                                              Unknown
                                            </option>
                                            <option value="needs-review">
                                              Needs review
                                            </option>
                                            <option value="confirmed">
                                              Confirmed
                                            </option>
                                          </select>
                                        )}
                                      </Field>
                                    </div>
                                    {text(
                                      "License / permission note",
                                      s.permissionNote,
                                      (v) =>
                                        source(s.id, { permissionNote: v }),
                                      "Record the license or permission basis.",
                                      true,
                                    )}
                                  </div>
                                ))}
                                <button
                                  className="secondary add-source"
                                  type="button"
                                  onClick={() =>
                                    update({
                                      sources: [
                                        ...p.sources,
                                        {
                                          id: crypto.randomUUID(),
                                          name: "",
                                          reference: "",
                                          language: "",
                                          permissionNote: "",
                                          permission: "unknown",
                                        },
                                      ],
                                    })
                                  }
                                >
                                  <Plus size={16} />
                                  Add data source
                                </button>
                                <small className="muted">
                                  Metadata only. Dataset contents and
                                  credentials are not stored here.
                                </small>
                              </div>
                            )}
                            {section === 4 && (
                              <div className="form-fields">
                                {text(
                                  "What does success look like?",
                                  p.successCriteria.qualityNotes,
                                  (v) => criteria({ qualityNotes: v }),
                                  "e.g. Produce coherent Bangla sentences on 20 fixed prompts with limited repetition.",
                                  true,
                                )}
                                <div className="divider-label">
                                  OPTIONAL NUMERIC TARGETS
                                </div>
                                <div className="field-grid">
                                  {numeric(
                                    "Held-out loss",
                                    p.successCriteria.heldOutLoss,
                                    (v) => criteria({ heldOutLoss: v }),
                                    "Held-out loss",
                                    true,
                                  )}
                                  {numeric(
                                    "Perplexity",
                                    p.successCriteria.perplexity,
                                    (v) => criteria({ perplexity: v }),
                                    "Perplexity",
                                  )}
                                  {numeric(
                                    "Maximum latency (ms)",
                                    p.successCriteria.maxLatencyMs,
                                    (v) => criteria({ maxLatencyMs: v }),
                                    "Latency",
                                  )}
                                  {numeric(
                                    "Maximum memory (GB)",
                                    p.successCriteria.maxMemoryGb,
                                    (v) => criteria({ maxMemoryGb: v }),
                                    "Memory limit",
                                  )}
                                </div>
                                <div className="info-note">
                                  <Gauge size={18} />
                                  <span>
                                    Loss and perplexity depend on a consistent
                                    tokenizer and evaluation setup. Leave these
                                    blank until you have a baseline.
                                  </span>
                                </div>
                              </div>
                            )}
                            {section === 5 && (
                              <div className="form-fields">
                                <div className="review-summary">
                                  <h3>{p.name || "Untitled project"}</h3>
                                  <p>
                                    {p.description || "No description added."}
                                  </p>
                                  <dl>
                                    <div>
                                      <dt>Task</dt>
                                      <dd>
                                        {p.task ? taskNames[p.task] : "Not set"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Language</dt>
                                      <dd>
                                        {p.language
                                          ? languageNames[p.language]
                                          : "Not set"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Objective</dt>
                                      <dd>{p.objective || "Not set"}</dd>
                                    </div>
                                    <div>
                                      <dt>Hardware</dt>
                                      <dd>
                                        {p.hardware.status === "entered"
                                          ? `${p.hardware.gpuModel || "GPU not set"} · ${p.hardware.gpuCount ?? "—"} GPU · ${p.hardware.vramPerGpuGb ?? "—"} GB VRAM each · ${p.hardware.ramGb ?? "—"} GB RAM · ${p.hardware.freeDiskGb ?? "—"} GB disk`
                                          : "Not checked yet"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Execution</dt>
                                      <dd>
                                        {p.hardware.location || "Not set"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Budget</dt>
                                      <dd>
                                        {p.budget.maxHours ?? "—"} hours ·{" "}
                                        {p.budget.maxCost ?? "Not set"}{" "}
                                        {p.budget.currency}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Sources</dt>
                                      <dd>
                                        {p.sources.length
                                          ? p.sources
                                              .map(
                                                (s) =>
                                                  `${s.name || "Unnamed"} (${s.permission})`,
                                              )
                                              .join(", ")
                                          : "None recorded"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Success</dt>
                                      <dd>
                                        {p.successCriteria.qualityNotes ||
                                          "Not set"}
                                      </dd>
                                    </div>
                                    <div>
                                      <dt>Targets</dt>
                                      <dd>
                                        Loss:{" "}
                                        {p.successCriteria.heldOutLoss ?? "—"} ·
                                        Perplexity:{" "}
                                        {p.successCriteria.perplexity ?? "—"} ·
                                        Latency:{" "}
                                        {p.successCriteria.maxLatencyMs ?? "—"}{" "}
                                        ms · Memory:{" "}
                                        {p.successCriteria.maxMemoryGb ?? "—"}{" "}
                                        GB
                                      </dd>
                                    </div>
                                  </dl>
                                </div>
                                <div className="review-checks">
                                  {state!.checks.map((c, i) => (
                                    <button
                                      type="button"
                                      key={c.title}
                                      onClick={() => setSection(i)}
                                    >
                                      {c.complete ? (
                                        <Check className="green" size={19} />
                                      ) : (
                                        <Circle size={17} />
                                      )}
                                      <span>
                                        <strong>{c.title}</strong>
                                        <small>{c.detail}</small>
                                      </span>
                                      <span
                                        className={`check-status ${c.complete ? "done" : ""}`}
                                      >
                                        {c.complete
                                          ? "Complete"
                                          : "Needs attention"}
                                      </span>
                                      <ChevronRight size={15} />
                                    </button>
                                  ))}
                                </div>
                                {issues.length > 0 && (
                                  <div className="field-error" role="alert">
                                    Fix invalid numeric values before saving:{" "}
                                    {issues.map((i) => i.field).join(", ")}.
                                  </div>
                                )}
                                <div className="info-note">
                                  <ShieldCheck size={18} />
                                  <span>
                                    Scope ready means your requirements are
                                    recorded. It does not verify your
                                    environment or start training.
                                  </span>
                                </div>
                              </div>
                            )}
                            <div className="form-footer">
                              <button
                                className="secondary"
                                type="submit"
                                disabled={saving || issues.length > 0}
                              >
                                <Save size={16} />
                                {saving ? "Saving…" : "Save draft"}
                              </button>
                              <div>
                                {section > 0 && (
                                  <button
                                    className="text-button"
                                    type="button"
                                    onClick={() => setSection(section - 1)}
                                  >
                                    Back
                                  </button>
                                )}
                                {section < 5 ? (
                                  <button
                                    className="primary"
                                    type="button"
                                    onClick={() => setSection(section + 1)}
                                  >
                                    Continue
                                    <ArrowRight size={16} />
                                  </button>
                                ) : (
                                  <button
                                    className="primary"
                                    type="button"
                                    disabled={!state!.ready || saving}
                                    onClick={() => void save(true)}
                                  >
                                    Mark scope ready
                                    <Check size={16} />
                                  </button>
                                )}
                              </div>
                            </div>
                          </fieldset>
                        </form>
                      </section>
                    </div>
                  </>
                )
              ) : page === "Environment" ? (
                <Environment
                  project={p}
                  onApply={(hardware) => update({ hardware })}
                  onSetup={() => navigate("Project Setup")}
                />
              ) : (
                <section className="empty-card planned-page">
                  <span className="planned-icon">
                    <FlaskConical size={30} />
                  </span>
                  <span className="pill">PLANNED</span>
                  <h2>{page} comes next.</h2>
                  <p>
                    We’re building the foundation first. Complete your project
                    scope before moving further along the training roadmap.
                  </p>
                  <button
                    className="primary"
                    onClick={() => navigate("Project Setup")}
                  >
                    Back to project setup
                    <ArrowRight size={16} />
                  </button>
                </section>
              )}
              <footer className="workspace-footer">
                <span>A workspace for curious builders.</span>
                <span>Scratch → Pre-train → Fine-tune</span>
              </footer>
            </>
          )}
        </main>
      </div>
      {pending && (
        <div className="modal-backdrop">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="leave-title"
          >
            <span className="modal-icon">
              <PanelLeftClose size={24} />
            </span>
            <h2 id="leave-title">Save before you leave?</h2>
            <p>
              Your changes haven’t been saved. Save your draft, discard changes,
              or stay here to keep editing.
            </p>
            <div role="alert">
              {error && <p className="field-error">{error}</p>}
            </div>
            <div className="modal-actions">
              <button
                className="text-button"
                disabled={saving}
                onClick={() => setPending(null)}
              >
                Keep editing
              </button>
              <button
                className="secondary"
                disabled={saving}
                onClick={() => {
                  setError("");
                  setProject(JSON.parse(savedJson) as Project | null);
                  void applyNavigation(pending);
                  setPending(null);
                  setNotice("");
                }}
              >
                Discard changes
              </button>
              <button
                className="primary"
                disabled={saving}
                onClick={async () => {
                  if (await save()) {
                    void applyNavigation(pending);
                    setPending(null);
                  }
                }}
              >
                Save & leave
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

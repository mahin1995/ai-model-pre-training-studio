# Step 1 — Pre-training Studio UI Plan

## 1. Goal ebong scope

Prothome React diye Pre-training Studio-r usable UI banabo. Python backend pore connect korbo. Ei step-e training run shuru hobe na.

Original roadmap-e Phase 0 holo scope, hardware ebong budget; Phase 1 holo environment setup. Ei document-er “Step 1” mane app development-er prothom milestone: oi requirements collect korar UI ebong studio-r navigation shell.

**Deliverable:** Mock data diye runnable, responsive React UI; project create/edit, setup checklist ebong saved draft thakbe.

## 2. Architecture

- Frontend: React + TypeScript + Vite.
- Styling: Tailwind CSS; reusable form, card, badge, modal ebong navigation components.
- Backend: Python + FastAPI, UI complete howar por implement korbo.
- Ekta repository-te `frontend/` ebong `backend/` thakbe.
- Development-e React dev server ebong Python API alada process-e cholbe; frontend `/api` request backend-e proxy korbe.
- Ekta command diye duita process start korar setup backend integration-er shomoy add korbo.
- Production-e single server chaile FastAPI built React assets ebong API dutoi serve korbe.
- Prothom UI-te mock service adapter use korbo, jate components change na kore pore real API connect kora jay.

## 3. UI layout

Desktop-e left sidebar, top project bar ebong main workspace thakbe. Mobile-e sidebar drawer hobe; form ebong cards single column-e ashbe.

Sidebar roadmap:

1. Overview
2. Project Setup — ei milestone-e fully functional
3. Environment
4. Datasets
5. Tokenizer
6. Model Config
7. Pre-training
8. Evaluation
9. Fine-tuning
10. Playground

Future sections-e clear “Planned” state thakbe. Training-related controls active dekhabe na.

## 4. Screen A — Overview

- Project na thakle “Create project” action-shoho empty state.
- Project thakle name, target task, language ebong setup completion summary.
- Setup checklist: scope, hardware, budget, data sources, success criteria.
- “Continue setup” action incomplete section-e niye jabe.
- Next milestone: environment verification.
- Real backend chara live GPU metrics, training loss ba model progress dekhabo na.

## 5. Screen B — Project Setup

### A. Basic information

- Project name — required.
- Description — optional.
- Target task — text completion, chatbot, domain assistant.
- Language — Bangla, English, mixed.
- Primary objective — learning/research ba specific task.

### B. Hardware ebong execution

- Training location — local ba cloud.
- GPU model, GPU count, VRAM per GPU.
- System RAM ebong free disk space.
- Hardware unknown hole “Not checked yet” select kora jabe; draft save hobe, readiness incomplete thakbe.
- UI-only version-e manual input; auto-detection backend milestone-e.
- Model size ekhono auto-finalize hobe na; hardware verification ebong pilot run-er por decide korbo.

### C. Budget

- Maximum training time in hours.
- Maximum monetary budget ebong currency.
- Local training-er jonno monetary budget optional; zero valid value.
- UI-te budget record korbo; automatic cost estimate ba enforcement ei milestone-er scope na.

### D. Data sources

- Existing data ache kina.
- Repeatable source rows: name, URL/path reference, language, license/permission note.
- Source usage permission: confirmed, needs review, unknown.
- Ei step-e source metadata save hobe; dataset upload, download ba scanning hobe na.

### E. Success criteria

- Held-out loss/perplexity target — optional, evaluation setup-er upor dependent.
- Qualitative prompt/task criteria — text field.
- Desired latency ebong memory limits — optional.
- Numeric criteria ekhono jana na thakle draft incomplete rekhe save kora jabe.

### F. Review ebong readiness

- Entered values-er summary.
- Missing required information-er checklist.
- Save draft action always available for valid partial data.
- “Mark scope ready” sudhu required scope, hardware, budget/time, source permission ebong success criteria complete hole enabled hobe.
- Scope ready mane requirements recorded; environment verified ba training-ready na.

## 6. Interaction ebong state

- Clear field labels, helper text ebong inline validation.
- Negative hardware/time/budget reject korbo; count positive integer hote hobe.
- Draft save-er por confirmation ebong last-saved timestamp.
- First version-e localStorage-e project metadata save korbo; reload korle restore hobe.
- localStorage unavailable/corrupt hole recovery message ebong usable empty state thakbe.
- Unsaved edits thakle internal navigation-e warning thakbe.
- Loading, empty, validation error, save failure ebong saved states design korbo.
- Keyboard navigation, visible focus, semantic labels ebong readable contrast thakbe.
- Browser storage-e secrets, credentials ba dataset contents rakha hobe na.

## 7. Data contract-er draft

Project shape:

```ts
type Project = {
  id: string;
  name: string;
  description: string;
  task: 'completion' | 'chatbot' | 'domain-assistant' | null;
  language: 'bn' | 'en' | 'mixed' | null;
  objective: string;
  hardware: {
    location: 'local' | 'cloud' | null;
    status: 'unknown' | 'entered';
    gpuModel: string;
    gpuCount: number | null;
    vramPerGpuGb: number | null;
    ramGb: number | null;
    freeDiskGb: number | null;
  };
  budget: { maxHours: number | null; maxCost: number | null; currency: string };
  hasExistingData: boolean | null;
  sources: Array<{
    id: string;
    name: string;
    reference: string;
    language: string;
    permissionNote: string;
    permission: 'confirmed' | 'needs-review' | 'unknown';
  }>;
  successCriteria: {
    qualityNotes: string;
    heldOutLoss: number | null;
    perplexity: number | null;
    maxLatencyMs: number | null;
    maxMemoryGb: number | null;
  };
  status: 'draft' | 'scope-ready';
  updatedAt: string;
};
```

Readiness ebong completion percentage ekta shared validation function theke calculate hobe. Backend add hole server abar validate korbe; client-er status trust korbe na.

Future API draft, ei milestone-e implement hobe na:

- `GET /api/health`
- `POST /api/projects`
- `GET /api/projects/{id}`
- `PATCH /api/projects/{id}`

Hardware discovery ebong environment checks-er API porer milestone-e define korbo.

## 8. Proposed structure

```text
pre-training-studio/
├── MODEL_TRAINING_PLAN.md
├── STEP_1_UI_PLAN.md
├── frontend/
│   └── src/
│       ├── components/
│       ├── layouts/
│       ├── pages/
│       ├── features/project-setup/
│       ├── services/
│       └── types/
└── backend/                 # Python API, porer milestone-e
```

Ei document chara proposed app folders ekhono create kora hoyni.

## 9. Implementation order

1. React/TypeScript scaffold, scripts ebong base styles.
2. Responsive sidebar, project header ebong routes.
3. Overview empty state ebong project summary.
4. Project Setup sections ebong reusable fields.
5. Validation, readiness checklist ebong review screen.
6. Mock service, localStorage persistence ebong save/error states.
7. Responsive/accessibility polish ebong build verification.
8. UI review-er por Python API integration-er kaj.

## 10. Acceptance criteria

- [x] Frontend documented command diye locally run hoy.
- [x] Empty state theke project draft create kora jay.
- [x] Setup information edit/save kore reload-er por fire pawa jay.
- [x] Invalid values clear error dekhay; partial draft save kora jay.
- [x] Required fields incomplete hole scope ready mark kora jay na.
- [x] Unknown hardware ba unconfirmed source permission readiness block kore.
- [x] Future roadmap sections planned state dekhay.
- [x] Mobile ebong desktop layout usable; keyboard diye form complete kora jay.
- [x] Storage failure user-ke dekhano hoy, saved bole false confirmation deya hoy na.
- [x] Type check ebong production build pass kore.
- [x] Readiness validation ebong draft persistence-er meaningful checks pass kore.

## 11. Ei step-er por

Python backend, persistent project storage ebong real environment checks connect korbo. Tarpor data collection/cleaning, tokenizer, model config ebong training screens sequentially implement korbo. Main training roadmap-er phase order unchanged thakbe.

## 12. Implementation status

Step 1 React UI implemented. Run instructions: `README.md`. Production build, 12 validation/storage tests, desktop/mobile browser flows ebong checked screens-er automated accessibility checks pass koreche. Screenshots ebong verification notes `artifacts/` folder-e ache. Python API integration ekhono porer milestone.

# Siftwise

**Smart file organization & archive planning CLI.**  
Turn chaotic folders into clean, structured archives with confidence scores, rules, and residual refinement loops.

> Built for power users, hoarders, and anyone with a "Desktop\Stuff" problem.

---

## ✨ What Siftwise Does

- Scans a root folder and builds a **TreePlan** for how files *should* be organized
- Classifies files into labels (e.g. `documents`, `media`, `archives`, `finance`, etc.)
- Assigns **Actions**: `Move`, `Copy`, `Skip`, or `Suggest`
- Writes everything to structured artifacts under a `.sift` directory:
  - `TreePlan.json` – proposed folder structure
  - `Mapping.csv` – one row per file with label, confidence, action, target path
  - `PreviewCounts.csv` – summary of how many files per label/action
- Executes moves safely with:
  - Journaling
  - One-shot undo
  - Dry-run / what-if modes (planned)

The core idea:  
Run Siftwise over a messy folder → inspect the plan → execute →  
then iteratively refine **residuals** (unknowns / low-confidence files) until the mess is gone.

---

## 🧠 Concept: Residuals

Not every file should be moved on the first pass.

Siftwise treats low-confidence / unknown files as **residuals**:

- They are **flagged** in `Mapping.csv` (e.g. `IsResidual = True`, `Action = Skip`)
- They are **not moved** yet
- A later command (`refine-residuals`) re-analyzes just the residuals with tighter focus

The vision is: each pass reduces the residual pile until very little is left unresolved.

---

## 🚀 Quickstart

> **Status:** early alpha – core pipeline is working, but expect breaking changes.

```bash
git clone https://github.com/<your-username>/siftwise.git
cd siftwise
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -e .

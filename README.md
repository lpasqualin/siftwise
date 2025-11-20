# Siftwise

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Mac%20%7C%20Linux-blue)

**Smart file organization & archive planning CLI.**  
Turn "Desktop\Stuff" chaos into clean, structured archives – with confidence scores, rules, and residual refinement passes.

Siftwise is for people who hoard files, run out of folders, and still refuse to delete anything.  
Instead of shaming you, it helps you clean up intelligently.

---

## ✨ Key Ideas

- **Plan first, move later**  
  Siftwise scans your source folder and builds a *plan* (TreePlan + Mapping), instead of immediately shoving files around.

- **Confidence-driven actions**  
  Each file gets a label and confidence score. High-confidence ones get moved; low-confidence ones become **residuals** to revisit.

- **Residual refinement loops**  
  Residuals aren’t forgotten – they’re flagged and re-analyzed in focused passes until the “mystery pile” shrinks.

- **Safe execution with journaling**  
  Moves are executed from the plan with room for dry-runs and undo (journal layer is being expanded).

---

## 🧠 How It Works (High Level)

```text
                ┌─────────────────────────────┐
                │          Siftwise           │
                │  "What's in this mess?"     │
                └──────────────┬──────────────┘
                               │
                      draft-structure
                               │
               ┌───────────────┴────────────────┐
               │                                │
      ┌────────▼────────┐              ┌────────▼─────────┐
      │   Analyzer      │              │    Strategy       │
      │ (detectors,     │              │ (planner, rules,  │
      │  tokens, etc.)  │              │  actions, targets)│
      └────────┬────────┘              └────────┬──────────┘
               │                                │
      ┌────────▼────────────┐         ┌─────────▼─────────────┐
      │  TreePlan.json      │         │   Mapping.csv          │
      │  PreviewCounts.csv  │         │   (one row per file)   │
      └────────┬────────────┘         └─────────┬──────────────┘
               │                                │
                     review-structure           │
                                                │
                                         execute / undo
                                                │
                                      refine-residuals (loop)

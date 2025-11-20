“Turn chaos into clean structure — intelligently, safely, and repeatably.”

git clone https://github.com/lpasqualin/siftwise.git
cd siftwise

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -e .
This installs siftwise in editable mode so you can hack on it.

🚀 Quickstart Example
Example uses generic paths – replace with your own.

1) Draft a structure
Scan a messy source folder and write the plan to <dest>/.sift:

bash
Copy code
python -m siftwise.commands.cli draft-structure ^
  --root "C:\Users\Username\Desktop\ArchiveTest\Incoming" ^
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
This creates, under Sorted\.sift:

TreePlan.json – proposed folder structure

Mapping.csv – one row per file (label, confidence, action, target path, residual flag)

PreviewCounts.csv – summary of labels/actions

2) Review the proposed plan
bash
Copy code
python -m siftwise.commands.cli review-structure ^
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
You get a human-readable view of what Siftwise wants to do before it touches anything.

3) Execute the plan
bash
Copy code
python -m siftwise.commands.cli execute ^
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
Siftwise moves files according to Mapping.csv.
Low-confidence or unresolved files are typically marked as Skip and left in place.

4) Refine residuals
bash
Copy code
python -m siftwise.commands.cli refine-residuals ^
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
This command focuses on files flagged as residuals and tries again with a tighter view, gradually shrinking the “unknown” pile.

🧱 Project Structure
Current structure (simplified):

text
Copy code
siftwise/
  __init__.py

  analyze/
    __init__.py
    analyzer.py        # core classification pipeline
    detectors.py       # label detectors (extensions, tokens, etc.)
    cohesion.py        # folder cohesion / tree logic
    tokens.py          # tokenization helpers

  commands/
    __init__.py
    cli.py             # main CLI switchboard
    draft_structure.py # draft-structure command
    review_structure.py# review-structure command
    execute.py         # execute command
    refine_residuals.py# residual refinement command

  state/
    __init__.py
    io.py              # read/write TreePlan, Mapping, Preview
    journal.py         # execution journal & undo (WIP)

  strategy/
    __init__.py
    planner.py         # decides Action + TargetPath per file
    rules_engine.py    # rules overlay (optional)
    entities.py        # entity extraction hooks (WIP)
At the root:

text
Copy code
pyproject.toml      # packaging + entry points
requirements.txt    # Python deps
README.md
LICENSE
docs/               # architecture, roadmap, etc. (see below)
🎯 Project Goals
Short-term (0.x):

✅ Build a reliable core pipeline: analyze → plan → execute → refine

✅ Make residuals a first-class concept (known but not blindly moved)

✅ Provide clear, inspectable artifacts (.sift folder)

🔄 Tune confidence thresholds & defaults so “safe by default” feels good

🔄 Improve logs and summaries so non-engineers can trust what’s happening

Medium-term (1.x):

Smarter residual strategies (focused passes, label-aware rules)

Folder-cohesion moves that keep subtrees intact when possible

Rule learning from edits to Mapping.csv / user overrides

Cleaner UX around dry-run vs live execution and undo

Future / experimental:

Embedding-based filename similarity and semantic buckets

Optional LLM-assisted classification & explanations

“Focused scan” mode that keeps working a target folder until little/no residuals remain

GUI or web front-end for non-CLI users

🤝 Contributing
Right now this is a young, evolving project. If you want to help:

Fork the repo

Create a feature branch:

bash
Copy code
git checkout -b feature/my-idea
Make your changes with clear commits

Run any available tests (when test suite lands)

Open a Pull Request with a short description and examples

Bug reports, weird edge cases, and “this path naming is cursed” issues are welcome.

👤 Author
Built by Leo Pasqualin

Working on practical AI tools for messy real-world workflows.
If Siftwise helped you clean something you were afraid to look at, it’s doing its job.

🔐 License
Siftwise is released under the MIT License.

sql
Copy code

You can soften or crank up the Leo tone later, but this is a solid v1.

---

## 3️⃣ `/docs` folder skeleton

Add a `docs/` directory at the repo root with a couple of simple starter files.

### `docs/ARCHITECTURE.md`

```markdown
# Siftwise Architecture

Siftwise is structured around a simple pipeline:

1. **Analyze**  
   - Walk the filesystem from a root path  
   - Run detectors to infer labels and confidence scores  
   - Build a flat list of `Result` objects

2. **Strategy / Planning**  
   - Convert analyzer results into:
     - `TreePlan.json` (proposed folder hierarchy)
     - `Mapping.csv` (one row per file with label, confidence, action, target path)
   - Apply rules and entity extraction where available

3. **State / Artifacts**  
   - All planning artifacts live inside a `.sift` folder under the chosen `dest_root`
   - This keeps the "brain" separate from the files being moved

4. **Execution**  
   - Read `Mapping.csv`
   - Perform `Move` / `Copy` actions with journaling
   - Leave `Skip` and residuals untouched

5. **Refinement**  
   - Identify residual files (low-confidence, unknown, or explicitly marked)
   - Re-run analysis on a smaller, focused set
   - Update `Mapping.csv` and artifacts

The long-term goal is to treat Siftwise as an "archive planning engine" that can be wrapped by CLIs, GUIs, and cloud serv

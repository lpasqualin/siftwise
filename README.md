# Siftwise

Turn chaos into clean structure --- intelligently, safely, and
repeatably.

## 🚀 Installation

``` bash
git clone https://github.com/lpasqualin/siftwise.git
cd siftwise

python -m venv .venv
```

Activate your virtual environment:

**Windows**

``` powershell
.venv\Scripts\activate
```

**macOS / Linux**

``` bash
source .venv/bin/activate
```

Install Siftwise in editable mode:

``` bash
pip install -e .
```

## 🚀 Quickstart

Replace sample paths with your own.

### 1) Draft a structure

``` powershell
python -m siftwise.commands.cli draft-structure `
  --root "C:\Users\Username\Desktop\ArchiveTest\Incoming" `
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
```

Creates:

-   `TreePlan.json`
-   `Mapping.csv`
-   `PreviewCounts.csv`

### 2) Review the proposed plan

``` powershell
python -m siftwise.commands.cli review-structure `
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
```

### 3) Execute the plan

``` powershell
python -m siftwise.commands.cli execute `
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
```

### 4) Refine residuals

``` powershell
python -m siftwise.commands.cli refine-residuals `
  --dest-root "C:\Users\Username\Desktop\ArchiveTest\Sorted"
```

## 🧱 Project Structure

    siftwise/
      analyze/
        analyzer.py
        detectors.py
        cohesion.py
        tokens.py

      commands/
        cli.py
        draft_structure.py
        review_structure.py
        execute.py
        refine_residuals.py

      strategy/
        planner.py
        rules_engine.py
        entities.py

      state/
        io.py
        journal.py

Root files:

    pyproject.toml
    requirements.txt
    README.md
    LICENSE
    docs/

## 🎯 Goals

### Short-term (0.x)

-   Solid core pipeline
-   Residuals treated cleanly
-   Safer defaults
-   Better logs

### Medium-term (1.x)

-   Residual refinement strategies
-   Folder-cohesion moves
-   Rule-learning from user edits
-   Improved dry-run & undo

### Future

-   Embedding similarity
-   Optional LLM classification
-   Focused multi-pass scan mode
-   GUI/web interface

## 🤝 Contributing

1.  Fork the repo

2.  Create a feature branch:

    ``` bash
    git checkout -b feature/my-feature
    ```

3.  Make changes

4.  Submit PR with description

## 👤 Author

Built by **Leo Pasqualin** --- practical AI tools for messy real‑world
workflows.

## 🔐 License

MIT License.

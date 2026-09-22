# Contributing to DisSModel

Thank you for your interest in contributing to DisSModel! We welcome contributions from research group members, students, and the broader open-source community.

---

## Contribution Workflow

We follow a **Trunk-Based Development** model: all active development targets the `main` branch through short-lived branches and Pull Requests.

### 1. Issues First
Before writing code or opening a pull request, make sure an issue tracks the task:
- Navigate to the **Issues** tab and click **New issue**.
- Choose the relevant template (**Feature Task**, **Bug Report**, **Documentation**, or **Onboarding**).
- Provide the required details. Relevant labels will be attached automatically.

### 2. Creating Your Branch

#### For Lab Members & Collaborators (Direct Access)
1. Open the assigned issue on GitHub.
2. In the right sidebar under **Development**, click **"Create a branch"**.
3. Use conventional prefixes: `feat/<issue-id>-short-desc`, `fix/<issue-id>-short-desc`, `docs/<issue-id>-short-desc`, or `chore/<issue-id>-short-desc`.
4. Pull and checkout the branch locally:
   ```bash
   git fetch origin
   git checkout <branch-name>

```

#### For External Contributors (Fork Workflow)

1. Fork the repository to your personal GitHub account.
2. Clone your fork locally:
```bash
git clone https://github.com/<your-username>/dissmodel.git
cd dissmodel

```


3. Create a descriptive feature branch targeting `main`:
```bash
git checkout -b feat/my-improvement

```



---

### 3. Submitting a Pull Request (PR)

1. Verify that all tests pass locally:
```bash
pytest tests/

```


2. Push your branch to GitHub:
* **Lab members:** `git push -u origin <branch-name>`
* **External contributors:** `git push -u origin feat/my-improvement` (to your fork)


3. Open a Pull Request targeting `DisSModel/dissmodel:main`.
4. Complete the checklist provided by the Pull Request template.
5. Ensure the PR description explicitly links the issue it resolves (e.g., `Closes #15`).
6. A maintainer will review your submission. Once approved, the changes will be integrated via **Squash and merge**, and the working branch will be automatically deleted.

---

## Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/DisSModel/dissmodel.git
cd dissmodel

```

### 2. Virtual Environment Setup

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

```

### 3. Install Development Dependencies

```bash
pip install -e ".[dev]"

```

### 4. Running the Test Suite

```bash
pytest tests/

```

---

## Coding Standards

* **PEP 8 Compliance:** Follow standard Python formatting conventions.
* **Type Annotations:** Provide type hints for public functions, methods, and class attributes.
* **Docstrings:** Document new modules, classes, and functions using NumPy docstring style.

---

## Documentation & Docstrings

Examples in NumPy-style docstrings using `>>>` prompts are executed as doctests during CI (`pytest --doctest-modules dissmodel`). They must be completely self-contained and runnable:

* Every referenced variable or module must be defined/imported within the example itself.
* Expected outputs must match the runtime output precisely.

Longer illustrative examples that depend on broader context (such as an existing GeoDataFrame, `Environment`, or simulation model instance) must use plain ````python` fenced code blocks instead of `>>>` interactive prompts. `mkdocstrings` renders both formats cleanly in the online API reference.

---

## Troubleshooting: Accidentally Committed to `main`?

If you committed directly to your local `main` branch and your push was blocked by repository rules, migrate your changes to a feature branch without losing work:

```bash
# 1. Create a new branch preserving your unpushed commits
git branch feat/<issue-id>-my-task

# 2. Reset your local main back to the clean remote state
git reset --hard origin/main

# 3. Switch to your new branch and push
git checkout feat/<issue-id>-my-task
git push -u origin feat/<issue-id>-my-task

```

---

## License

By contributing to DisSModel, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).



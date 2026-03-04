# Git Tracking Specification

This document specifies the Git tracking rules and conventions for the Task Manager project.

## Ignored Files & Directories (`.gitignore`)

The following types of files and directories must NOT be tracked by Git. They are explicitly ignored in the `.gitignore` file.

### 1. Python Environment & Compilation
- `__pycache__/`, `*.py[cod]`, `*$py.class`: Compiled Python byte code.
- `venv/`, `.venv/`, `env/`: Virtual environment directories.
- `build/`, `dist/`, `*.egg-info/`, `*.egg`: Packaging and distribution artifacts.

### 2. Secrets & Environment Variables (SECURITY CRITICAL)
- `.env`, `.env.local`: Environment variable files containing sensitive configuration.
- `credentials.json`, `token.json`, `oauth_token.txt`, `client_secret_*.json`: Google API credentials and OAuth tokens. **These must never be committed.**

### 3. Application State & Data
- `data/state.json`: The application's local state file, which changes frequently during runtime.
- `data/token.json`: Generated API tokens stored by the application.
- `*.log`: Application runtime log files.

### 4. Testing & Static Analysis Caches
- `.pytest_cache/`, `.coverage`, `htmlcov/`: Test execution and coverage caches.
- `.mypy_cache/`, `.ruff_cache/`: Type checking and linting caches.

### 5. IDE & OS Specific Files
- `.vscode/`: Visual Studio Code workspace settings (unless explicitly shared settings are desired).
- `.idea/`: JetBrains IDE (PyCharm, etc.) project settings.
- `.DS_Store`: macOS custom directory attributes.
- `Thumbs.db`: Windows image thumbnail cache.

## Empty Directory Tracking

Git does not track empty directories. If the application requires a directory to exist for runtime operation (e.g., a place to store generated files), and that directory is otherwise empty or its contents are ignored, a `.gitkeep` file should be placed inside it and tracked.

- `data/.gitkeep`: Ensures the `data/` directory is present in the repository and cloned to new environments, even though files like `state.json` inside it are ignored.

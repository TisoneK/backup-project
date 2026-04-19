# Backup Project

A cross-platform Python tool to back up any project directory to a timestamped ZIP in `~/Downloads/backup/`, automatically excluding common development noise.

**Zero dependencies — pure Python stdlib.**

## Features

- 🎯 **Simple usage**: `backup_project` from any directory
- 📁 **Auto-save**: Backups go to `~/Downloads/backup/{project-name}-{timestamp}.zip`
- 🚫 **Smart exclusions**: Skips `.venv`, `node_modules`, `__pycache__`, `.git`, `.env` files, and much more
- 🌍 **Cross-platform**: Works on Windows, macOS, and Linux
- 🔍 **Dry-run mode**: Preview what would be backed up without creating a ZIP
- ⚙️ **Configurable**: Per-project `.backuprc` files for custom exclusions
- 📦 **Zero dependencies**: No pip installs needed — pure Python stdlib

## Quick Start

### Install

```bash
# Clone or download the project, then:
python install.py
```

Restart your terminal, then use `backup_project` from anywhere.

To uninstall:

```bash
python install.py uninstall
```

### Use

```bash
backup_project                          # back up the current directory
backup_project /path/to/project         # back up a specific directory
backup_project --dry-run                # preview without creating a ZIP
backup_project -o ~/my-backup.zip       # custom output path
backup_project --config ~/.backuprc     # use a specific config file
backup_project --help                   # full usage
```

### Or run directly (no install needed)

```bash
python backup_project.py
python backup_project.py /path/to/project
python backup_project.py --dry-run
```

## Example output

```
Starting backup...
  Source:      /Users/tison/Dev/localmind
  Destination: /Users/tison/Downloads/backup/localmind-20260419-104224.zip
  Files found: 98

Backup created successfully!
  File:  /Users/tison/Downloads/backup/localmind-20260419-104224.zip
  Size:  0.12 MB
  Files: 98
```

Dry-run output:

```
DRY RUN — Backup Preview
==================================================
  Source:      /Users/tison/Dev/localmind
  Destination: /Users/tison/Downloads/backup/localmind-20260419-104224.zip

Files that WOULD be backed up:
  Count: 98
  Size:  1.43 MB (uncompressed)

Excluded directories:
  ✗ .venv/         (312 files)
  ✗ node_modules/  (1247 files)
  ✗ __pycache__/   (23 files)
  ✗ .git/          (89 files)

Sample of included files (first 20 of 98):
  ✓ README.md   (4.5 KB)
  ✓ src/main.py (2.1 KB)
  …
```

## What gets excluded

### Directories (entire subtree skipped)

| Category | Directories |
|---|---|
| Python | `.venv`, `venv`, `env`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.nox`, `htmlcov`, `.pyre`, `.pytype` |
| Node.js | `node_modules`, `bower_components`, `jspm_packages`, `web_modules`, `.npm`, `.pnpm-store`, `.parcel-cache`, `.svelte-kit`, `.vite`, `.next`, `.nuxt` |
| Build | `build`, `dist` |
| Coverage | `coverage`, `.nyc_output` |
| Cache / temp | `.cache`, `.tmp`, `temp`, `tmp`, `logs` |
| VCS | `.git`, `.hg`, `.svn` |
| IDEs | `.vscode`, `.vscode-test`, `.idea` |

### Files

| Category | Patterns |
|---|---|
| Secrets | `.env`, `.env.*`, `.envrc` |
| Bytecode | `*.pyc`, `*.pyo`, `*.pyd`, `*.so` |
| Logs | `*.log` |
| Windows | `Thumbs.db`, `Desktop.ini`, `*.lnk`, `*.msi`, …  |
| macOS | `.DS_Store`, `._*`, `__MACOSX/`, … |

## Custom exclusions via `.backuprc`

Place a `.backuprc` file in your project root (or pass `--config`) to add your own rules:

```json
{
  "exclude_dirs":       ["my-cache", "scratch"],
  "exclude_names":      ["secrets.json"],
  "exclude_extensions": [".bak"],
  "exclude_patterns":   ["migration_snapshots[/\\\\]"],
  "include_defaults":   true,
  "backup_dir":         "~/my-backups",
  "compression":        "deflated"
}
```

See `.backuprc.example` for a fully documented template.

**Options:**

| Key | Type | Default | Description |
|---|---|---|---|
| `exclude_dirs` | list | `[]` | Extra directory names to skip |
| `exclude_names` | list | `[]` | Extra filenames to skip |
| `exclude_extensions` | list | `[]` | Extra extensions to skip (e.g. `".bak"`) |
| `exclude_patterns` | list | `[]` | Extra regex patterns matched against the relative path |
| `include_defaults` | bool | `true` | Whether to keep the built-in exclusion list |
| `backup_dir` | string | `~/Downloads/backup` | Where to save the ZIP |
| `compression` | string | `"deflated"` | `deflated` / `stored` / `bzip2` / `lzma` |

## Project structure

```
backup-project/
├── backup_project.py       ← main script (zero dependencies)
├── install.py              ← cross-platform installer
├── pyproject.toml          ← packaging metadata
├── .backuprc.example       ← config file template
├── README.md
└── tests/
    └── test_backup.py      ← pytest suite
```

## Development

### Run the tests

```bash
pip install pytest
pytest tests/ -v
```

With coverage:

```bash
pip install pytest pytest-cov
pytest tests/ -v --cov=backup_project --cov-report=term-missing
```

### Install in development mode (editable)

```bash
pip install -e ".[dev]"
```

## Roadmap

- [ ] Progress bar for large backups
- [ ] Incremental / differential backups
- [ ] Cloud storage integration (S3, Google Drive, Dropbox)
- [ ] Parallel file processing for very large projects
- [ ] Backup verification (checksum validation)
- [ ] Optional GUI (ttkbootstrap or PyQt6)

## License

MIT License — see LICENSE for details.

#!/usr/bin/env python3
"""
backup_project.py — Cross-platform project backup tool.

Backs up a project directory to a timestamped ZIP in ~/Downloads/backup/,
automatically excluding common development noise (node_modules, .venv, etc.).

Usage:
    python backup_project.py                    # backup current directory
    python backup_project.py /path/to/project   # backup specific directory
    python backup_project.py --dry-run          # preview without creating ZIP
    python backup_project.py --output ~/my.zip  # custom output path

Zero external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterator, NamedTuple

# ---------------------------------------------------------------------------
# Colour helpers (no deps — fall back gracefully on Windows without ANSI)
# ---------------------------------------------------------------------------

_ANSI = sys.stdout.isatty() and os.name != "nt" or (
    os.name == "nt"
    and os.environ.get("WT_SESSION")  # Windows Terminal
    or os.environ.get("TERM_PROGRAM") == "vscode"
)


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _ANSI else text


def green(t: str) -> str:  return _c("32", t)
def cyan(t: str) -> str:   return _c("36", t)
def yellow(t: str) -> str: return _c("33", t)
def red(t: str) -> str:    return _c("31", t)
def bold(t: str) -> str:   return _c("1",  t)
def dim(t: str) -> str:    return _c("2",  t)


# ---------------------------------------------------------------------------
# Default exclusion rules
# ---------------------------------------------------------------------------

# Entire directory subtrees to skip — matched against the directory *name*
# (not the full path), so they're platform-independent.
DEFAULT_EXCLUDED_DIRS: frozenset[str] = frozenset([
    # Python
    ".venv", "venv", "env", ".env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", ".nox", "htmlcov", ".pyre", ".pytype",
    # Node.js / JS
    "node_modules", "bower_components", "jspm_packages", "web_modules",
    ".npm", ".pnpm-store", ".parcel-cache", ".svelte-kit", ".vite",
    ".next", ".nuxt",
    # Build / output
    "build", "dist",
    # Coverage
    "coverage", ".nyc_output",
    # Caches / temp
    ".cache", ".tmp", "temp", "tmp", "logs",
    # Version control
    ".git", ".hg", ".svn",
    # IDEs
    ".vscode", ".vscode-test", ".idea",
    # macOS
    "__MACOSX",
    # Windows
    "$RECYCLE.BIN",
])

# Individual file names to always skip
DEFAULT_EXCLUDED_NAMES: frozenset[str] = frozenset([
    # Windows
    "Thumbs.db", "ehthumbs.db", "ehthumbs_vista.db", "Desktop.ini",
    # macOS
    ".DS_Store", ".localized",
    # Misc
    ".eslintcache", ".stylelintcache", ".yarn-integrity",
])

# File extensions to always skip
DEFAULT_EXCLUDED_EXTENSIONS: frozenset[str] = frozenset([
    # Python bytecode
    ".pyc", ".pyo", ".pyd",
    # Compiled / binary
    ".so",
    # Node
    ".tgz",
    # Windows
    ".cab", ".msi", ".msix", ".msm", ".msp", ".lnk", ".stackdump",
    # Logs
    ".log",
    # macOS
    ".localized",
])

# Regex patterns for anything not captured above (matched against the full
# relative path string, using forward slashes regardless of OS)
DEFAULT_EXCLUDED_PATTERNS: list[str] = [
    # Python egg / dist-info
    r"\.egg-info[/\\]",
    # env files (secrets)
    r"(^|[/\\])\.env(\.[^/\\]+)?$",
    r"(^|[/\\])\.envrc$",
    # coverage data files
    r"(^|[/\\])\.coverage(\..+)?$",
    # Node pnp
    r"(^|[/\\])\.pnp(\..+)?$",
    # macOS AppleDouble / resource forks
    r"(^|[/\\])\._",
    r"(^|[/\\])\.AppleDouble",
    r"(^|[/\\])\.LSOverride",
    r"(^|[/\\])\.DocumentRevisions-V100",
    r"(^|[/\\])\.fseventsd",
    r"(^|[/\\])\.Spotlight-V100",
    r"(^|[/\\])\.TemporaryItems",
    r"(^|[/\\])\.Trashes",
    r"(^|[/\\])\.VolumeIcon\.icns",
    # spyder / rope
    r"(^|[/\\])\.spyderproject",
    r"(^|[/\\])\.ropeproject",
]


# ---------------------------------------------------------------------------
# Configuration file (.backuprc)
# ---------------------------------------------------------------------------

class BackupConfig(NamedTuple):
    """Parsed .backuprc configuration."""
    extra_dirs: list[str]
    extra_names: list[str]
    extra_extensions: list[str]
    extra_patterns: list[str]
    include_defaults: bool
    backup_dir: str | None
    compression: str  # "deflated" | "stored" | "bzip2" | "lzma"

    @staticmethod
    def default() -> "BackupConfig":
        return BackupConfig(
            extra_dirs=[], extra_names=[], extra_extensions=[],
            extra_patterns=[], include_defaults=True,
            backup_dir=None, compression="deflated",
        )


def load_config(config_path: Path) -> BackupConfig:
    """Load and validate a .backuprc JSON config file."""
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    compression_map = {
        "deflated": "deflated", "stored": "stored",
        "bzip2": "bzip2",       "lzma": "lzma",
    }
    compression = compression_map.get(
        str(raw.get("compression", "deflated")).lower(), "deflated"
    )

    def _str_list(key: str) -> list[str]:
        val = raw.get(key, [])
        if not isinstance(val, list):
            raise ValueError(f".backuprc '{key}' must be a list of strings")
        return [str(v) for v in val]

    return BackupConfig(
        extra_dirs=_str_list("exclude_dirs"),
        extra_names=_str_list("exclude_names"),
        extra_extensions=_str_list("exclude_extensions"),
        extra_patterns=_str_list("exclude_patterns"),
        include_defaults=bool(raw.get("include_defaults", True)),
        backup_dir=raw.get("backup_dir"),
        compression=compression,
    )


# ---------------------------------------------------------------------------
# Core backup logic
# ---------------------------------------------------------------------------

_COMPRESSION_MAP = {
    "deflated": zipfile.ZIP_DEFLATED,
    "stored":   zipfile.ZIP_STORED,
    "bzip2":    zipfile.ZIP_BZIP2,
    "lzma":     zipfile.ZIP_LZMA,
}


class ExclusionRules:
    """Compiled set of exclusion rules used during file collection."""

    def __init__(
        self,
        excluded_dirs: frozenset[str],
        excluded_names: frozenset[str],
        excluded_extensions: frozenset[str],
        compiled_patterns: list[re.Pattern],
    ) -> None:
        self.excluded_dirs = excluded_dirs
        self.excluded_names = excluded_names
        self.excluded_extensions = excluded_extensions
        self.compiled_patterns = compiled_patterns

    @classmethod
    def build(cls, config: BackupConfig) -> "ExclusionRules":
        if config.include_defaults:
            dirs = DEFAULT_EXCLUDED_DIRS | frozenset(config.extra_dirs)
            names = DEFAULT_EXCLUDED_NAMES | frozenset(config.extra_names)
            exts = DEFAULT_EXCLUDED_EXTENSIONS | frozenset(
                e if e.startswith(".") else f".{e}"
                for e in config.extra_extensions
            )
            patterns = DEFAULT_EXCLUDED_PATTERNS + config.extra_patterns
        else:
            dirs = frozenset(config.extra_dirs)
            names = frozenset(config.extra_names)
            exts = frozenset(
                e if e.startswith(".") else f".{e}"
                for e in config.extra_extensions
            )
            patterns = config.extra_patterns

        compiled = [re.compile(p) for p in patterns]
        return cls(dirs, names, exts, compiled)

    def is_dir_excluded(self, name: str) -> bool:
        return name in self.excluded_dirs

    def is_file_excluded(self, rel_path: str, name: str, suffix: str) -> bool:
        if name in self.excluded_names:
            return True
        if suffix.lower() in self.excluded_extensions:
            return True
        norm = rel_path.replace(os.sep, "/")
        return any(p.search(norm) for p in self.compiled_patterns)


def _walk(source: Path, rules: ExclusionRules) -> Iterator[Path]:
    """
    Yield files under *source* that pass the exclusion rules.

    Uses os.walk with in-place dir pruning so excluded subtrees are never
    descended into — much faster than rglob on large projects.
    """
    for dirpath, dirnames, filenames in os.walk(source):
        cur = Path(dirpath)

        # Prune excluded directories in-place (modifies the list os.walk uses)
        dirnames[:] = [
            d for d in dirnames
            if not rules.is_dir_excluded(d)
        ]

        for filename in filenames:
            file = cur / filename
            try:
                rel = file.relative_to(source)
            except ValueError:
                continue
            suffix = file.suffix
            if not rules.is_file_excluded(str(rel), filename, suffix):
                yield file


class ExclusionStats(NamedTuple):
    excluded_dirs: dict[str, int]   # dir name → file count
    excluded_files: int


def _walk_with_stats(
    source: Path, rules: ExclusionRules
) -> tuple[list[Path], ExclusionStats]:
    """Like _walk but also tracks what was excluded (for --dry-run)."""
    included: list[Path] = []
    excluded_dirs: dict[str, int] = {}
    excluded_files = 0

    for dirpath, dirnames, filenames in os.walk(source):
        cur = Path(dirpath)

        # Identify excluded dirs and count their files (shallow, not perfect,
        # but fast enough for a preview)
        removed = []
        kept = []
        for d in dirnames:
            if rules.is_dir_excluded(d):
                removed.append(d)
            else:
                kept.append(d)
        dirnames[:] = kept

        for d in removed:
            subtree = cur / d
            count = sum(1 for _ in subtree.rglob("*") if (subtree / _).is_file()
                        ) if subtree.is_dir() else 0
            try:
                count = sum(
                    1 for root2, _, files2 in os.walk(subtree)
                    for _ in files2
                )
            except PermissionError:
                count = 0
            excluded_dirs[d] = excluded_dirs.get(d, 0) + count

        for filename in filenames:
            file = cur / filename
            try:
                rel = file.relative_to(source)
            except ValueError:
                continue
            suffix = file.suffix
            if rules.is_file_excluded(str(rel), filename, suffix):
                excluded_files += 1
            else:
                included.append(file)

    return included, ExclusionStats(excluded_dirs, excluded_files)


def default_backup_dir() -> Path:
    """Return ~/Downloads/backup, creating it if needed."""
    path = Path.home() / "Downloads" / "backup"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_destination(source: Path, backup_dir: Path | None = None) -> Path:
    bdir = backup_dir if backup_dir else default_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return bdir / f"{source.name}-{timestamp}.zip"


def create_backup(
    source: Path,
    files: list[Path],
    destination: Path,
    compression: str = "deflated",
) -> None:
    """Write *files* into a ZIP at *destination*, preserving structure."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    zcomp = _COMPRESSION_MAP.get(compression, zipfile.ZIP_DEFLATED)

    total = len(files)
    interval = max(1, total // 20)  # update roughly every 5 %

    with zipfile.ZipFile(destination, "w", compression=zcomp) as zf:
        for i, file in enumerate(files, 1):
            arcname = file.relative_to(source)
            try:
                zf.write(file, arcname)
            except (PermissionError, OSError) as exc:
                print(yellow(f"  Warning: skipped {arcname} ({exc})"),
                      file=sys.stderr)

            if sys.stdout.isatty() and (i % interval == 0 or i == total):
                pct = int(i / total * 100)
                bar_fill = int(pct / 5)
                bar = "█" * bar_fill + "░" * (20 - bar_fill)
                print(f"\r  [{bar}] {pct:3d}%  {i}/{total} files",
                      end="", flush=True)

    if sys.stdout.isatty():
        print()  # newline after progress bar


# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def cmd_backup(args: argparse.Namespace) -> int:
    source = Path(args.project_dir).resolve()
    if not source.is_dir():
        print(red(f"Error: '{source}' is not a directory."), file=sys.stderr)
        return 1

    config = BackupConfig.default()
    rc_file = source / ".backuprc"
    if args.config:
        rc_file = Path(args.config)
    if rc_file.is_file():
        try:
            config = load_config(rc_file)
            print(dim(f"  Config: {rc_file}"))
        except ValueError as exc:
            print(red(f"Error: {exc}"), file=sys.stderr)
            return 1

    rules = ExclusionRules.build(config)

    # Determine destination
    if args.output:
        destination = Path(args.output).resolve()
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
    else:
        backup_dir_path: Path | None = None
        if config.backup_dir:
            backup_dir_path = Path(config.backup_dir).expanduser().resolve()
        destination = make_destination(source, backup_dir_path)

    print(bold(green("Starting backup...")))
    print(f"  {dim('Source:')}      {cyan(str(source))}")
    print(f"  {dim('Destination:')} {cyan(str(destination))}")

    files = list(_walk(source, rules))

    if not files:
        print(yellow("No files found after exclusions. Backup not created."))
        return 0

    print(f"  {dim('Files found:')}  {yellow(str(len(files)))}")

    create_backup(source, files, destination, config.compression)

    size_mb = destination.stat().st_size / (1024 * 1024)
    print(bold(green("\nBackup created successfully!")))
    print(f"  {dim('File:')}  {cyan(str(destination))}")
    print(f"  {dim('Size:')}  {yellow(f'{size_mb:.2f} MB')}")
    print(f"  {dim('Files:')} {yellow(str(len(files)))}")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    source = Path(args.project_dir).resolve()
    if not source.is_dir():
        print(red(f"Error: '{source}' is not a directory."), file=sys.stderr)
        return 1

    config = BackupConfig.default()
    rc_file = source / ".backuprc"
    if args.config:
        rc_file = Path(args.config)
    if rc_file.is_file():
        try:
            config = load_config(rc_file)
        except ValueError as exc:
            print(red(f"Error: {exc}"), file=sys.stderr)
            return 1

    rules = ExclusionRules.build(config)

    backup_dir_path: Path | None = None
    if config.backup_dir:
        backup_dir_path = Path(config.backup_dir).expanduser().resolve()
    destination = make_destination(source, backup_dir_path)
    if args.output:
        destination = Path(args.output).resolve()

    print(bold(yellow("DRY RUN — Backup Preview")))
    print("=" * 50)
    print(f"  {dim('Source:')}      {cyan(str(source))}")
    print(f"  {dim('Destination:')} {cyan(str(destination))}")
    print()

    files, stats = _walk_with_stats(source, rules)

    total_size = sum(f.stat().st_size for f in files if f.exists())
    size_mb = total_size / (1024 * 1024)

    print(bold("Files that WOULD be backed up:"))
    print(f"  Count: {yellow(str(len(files)))}")
    print(f"  Size:  {yellow(f'{size_mb:.2f} MB')} (uncompressed)")
    print()

    if stats.excluded_dirs:
        print(bold("Excluded directories:"))
        for dname, count in sorted(stats.excluded_dirs.items(),
                                   key=lambda kv: -kv[1]):
            print(f"  {red('✗')} {dname}/  {dim(f'({count} files)')}")
        print()

    if stats.excluded_files:
        print(f"  {dim('+ ')} {stats.excluded_files} individual files excluded by name/extension/pattern")
        print()

    # Show a sample of included files (up to 20)
    print(bold(f"Sample of included files (first 20 of {len(files)}):"))
    for f in files[:20]:
        rel = f.relative_to(source)
        size_kb = f.stat().st_size / 1024
        print(f"  {green('✓')} {rel}  {dim(f'({size_kb:.1f} KB)')}")
    if len(files) > 20:
        print(dim(f"  … and {len(files) - 20} more files"))

    print()
    print(dim("Run without --dry-run to create the actual backup."))
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backup_project",
        description="Back up a project directory to a timestamped ZIP, "
                    "automatically excluding common dev noise.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  backup_project                        backup current directory
  backup_project /path/to/project       backup a specific directory
  backup_project --dry-run              preview without creating ZIP
  backup_project -o ~/my-backup.zip     custom output path
  backup_project --config ~/.backuprc   use a specific config file
""",
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        metavar="DIR",
        help="project directory to back up (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview what would be backed up without creating a ZIP",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        help="custom path for the output ZIP file",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="path to a .backuprc config file "
             "(auto-detected in project root if omitted)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="backup_project 2.0.0",
    )
    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.dry_run:
            return cmd_dry_run(args)
        return cmd_backup(args)
    except KeyboardInterrupt:
        print(red("\nAborted."), file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(red(f"Unexpected error: {exc}"), file=sys.stderr)
        if os.environ.get("BACKUP_DEBUG"):
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())

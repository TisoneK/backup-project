"""
tests/test_backup.py — pytest test suite for backup_project.

Run with:  pytest tests/ -v
           pytest tests/ -v --tb=short
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

# Make sure the project root is importable regardless of how pytest is invoked
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backup_project import (
    BackupConfig,
    ExclusionRules,
    ExclusionStats,
    _walk,
    _walk_with_stats,
    create_backup,
    load_config,
    make_destination,
    default_backup_dir,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """
    A small fake project tree:

    myproject/
    ├── src/
    │   ├── main.py
    │   └── utils.py
    ├── tests/
    │   └── test_main.py
    ├── README.md
    ├── .env              ← should be excluded
    ├── __pycache__/      ← should be excluded
    │   └── main.cpython-311.pyc
    ├── .venv/            ← should be excluded
    │   └── lib/
    │       └── dummy.py
    └── node_modules/     ← should be excluded
        └── react/
            └── index.js
    """
    root = tmp_path / "myproject"
    # Included
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text("print('hello')")
    (root / "src" / "utils.py").write_text("def helper(): pass")
    (root / "tests").mkdir()
    (root / "tests" / "test_main.py").write_text("def test_nothing(): pass")
    (root / "README.md").write_text("# My Project")
    # Excluded
    (root / ".env").write_text("SECRET=hunter2")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"\x00" * 16)
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "dummy.py").write_text("")
    (root / "node_modules" / "react").mkdir(parents=True)
    (root / "node_modules" / "react" / "index.js").write_text("module.exports={}")
    return root


@pytest.fixture()
def default_rules() -> ExclusionRules:
    return ExclusionRules.build(BackupConfig.default())


# ---------------------------------------------------------------------------
# ExclusionRules — directory exclusions
# ---------------------------------------------------------------------------

class TestDirExclusion:
    def test_excludes_venv(self, default_rules):
        assert default_rules.is_dir_excluded(".venv")

    def test_excludes_node_modules(self, default_rules):
        assert default_rules.is_dir_excluded("node_modules")

    def test_excludes_pycache(self, default_rules):
        assert default_rules.is_dir_excluded("__pycache__")

    def test_excludes_git(self, default_rules):
        assert default_rules.is_dir_excluded(".git")

    def test_excludes_dist(self, default_rules):
        assert default_rules.is_dir_excluded("dist")

    def test_excludes_build(self, default_rules):
        assert default_rules.is_dir_excluded("build")

    def test_does_not_exclude_src(self, default_rules):
        assert not default_rules.is_dir_excluded("src")

    def test_does_not_exclude_tests(self, default_rules):
        assert not default_rules.is_dir_excluded("tests")


# ---------------------------------------------------------------------------
# ExclusionRules — file exclusions
# ---------------------------------------------------------------------------

class TestFileExclusion:
    def test_excludes_pyc(self, default_rules):
        assert default_rules.is_file_excluded("src/foo.pyc", "foo.pyc", ".pyc")

    def test_excludes_dot_env(self, default_rules):
        assert default_rules.is_file_excluded(".env", ".env", "")

    def test_excludes_dot_env_local(self, default_rules):
        assert default_rules.is_file_excluded(".env.local", ".env.local", "")

    def test_excludes_log_file(self, default_rules):
        assert default_rules.is_file_excluded("app.log", "app.log", ".log")

    def test_excludes_ds_store(self, default_rules):
        assert default_rules.is_file_excluded(".DS_Store", ".DS_Store", "")

    def test_excludes_thumbs_db(self, default_rules):
        assert default_rules.is_file_excluded("Thumbs.db", "Thumbs.db", "")

    def test_allows_py_file(self, default_rules):
        assert not default_rules.is_file_excluded("src/main.py", "main.py", ".py")

    def test_allows_readme(self, default_rules):
        assert not default_rules.is_file_excluded("README.md", "README.md", ".md")

    def test_allows_json(self, default_rules):
        assert not default_rules.is_file_excluded(
            "config/settings.json", "settings.json", ".json"
        )


# ---------------------------------------------------------------------------
# _walk — integration with a real temp project
# ---------------------------------------------------------------------------

class TestWalk:
    def test_included_files_collected(self, tmp_project, default_rules):
        files = set(_walk(tmp_project, default_rules))
        rel = {f.relative_to(tmp_project) for f in files}
        assert Path("src/main.py") in rel
        assert Path("src/utils.py") in rel
        assert Path("tests/test_main.py") in rel
        assert Path("README.md") in rel

    def test_env_file_excluded(self, tmp_project, default_rules):
        files = set(_walk(tmp_project, default_rules))
        names = {f.name for f in files}
        assert ".env" not in names

    def test_venv_dir_excluded(self, tmp_project, default_rules):
        files = list(_walk(tmp_project, default_rules))
        paths = [str(f) for f in files]
        assert not any(".venv" in p for p in paths)

    def test_pycache_excluded(self, tmp_project, default_rules):
        files = list(_walk(tmp_project, default_rules))
        paths = [str(f) for f in files]
        assert not any("__pycache__" in p for p in paths)

    def test_node_modules_excluded(self, tmp_project, default_rules):
        files = list(_walk(tmp_project, default_rules))
        # Use relative paths to avoid matching the pytest tmp dir name
        rel_paths = [str(f.relative_to(tmp_project)) for f in files]
        assert not any("node_modules" in p for p in rel_paths)

    def test_pyc_excluded(self, tmp_project, default_rules):
        files = list(_walk(tmp_project, default_rules))
        exts = {f.suffix for f in files}
        assert ".pyc" not in exts

    def test_file_count(self, tmp_project, default_rules):
        files = list(_walk(tmp_project, default_rules))
        # Included: main.py, utils.py, test_main.py, README.md = 4
        assert len(files) == 4


# ---------------------------------------------------------------------------
# _walk_with_stats
# ---------------------------------------------------------------------------

class TestWalkWithStats:
    def test_returns_same_files_as_walk(self, tmp_project, default_rules):
        included_walk = set(_walk(tmp_project, default_rules))
        included_stats, _ = _walk_with_stats(tmp_project, default_rules)
        assert set(included_stats) == included_walk

    def test_excluded_dirs_tracked(self, tmp_project, default_rules):
        _, stats = _walk_with_stats(tmp_project, default_rules)
        assert ".venv" in stats.excluded_dirs
        assert "node_modules" in stats.excluded_dirs
        assert "__pycache__" in stats.excluded_dirs

    def test_excluded_files_counted(self, tmp_project, default_rules):
        _, stats = _walk_with_stats(tmp_project, default_rules)
        # .env is excluded at file level (pattern match)
        assert stats.excluded_files >= 1


# ---------------------------------------------------------------------------
# create_backup
# ---------------------------------------------------------------------------

class TestCreateBackup:
    def test_creates_zip(self, tmp_project, tmp_path, default_rules):
        dest = tmp_path / "out.zip"
        files = list(_walk(tmp_project, default_rules))
        create_backup(tmp_project, files, dest)
        assert dest.is_file()
        assert dest.stat().st_size > 0

    def test_zip_contains_expected_entries(self, tmp_project, tmp_path, default_rules):
        dest = tmp_path / "out.zip"
        files = list(_walk(tmp_project, default_rules))
        create_backup(tmp_project, files, dest)

        with zipfile.ZipFile(dest) as zf:
            names = {n.replace("\\", "/") for n in zf.namelist()}

        assert "src/main.py" in names
        assert "src/utils.py" in names
        assert "README.md" in names

    def test_zip_excludes_sensitive_files(self, tmp_project, tmp_path, default_rules):
        dest = tmp_path / "out.zip"
        files = list(_walk(tmp_project, default_rules))
        create_backup(tmp_project, files, dest)

        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()

        assert all(".env" not in n for n in names)
        assert all(".venv" not in n for n in names)
        assert all("node_modules" not in n for n in names)

    def test_zip_preserves_directory_structure(self, tmp_project, tmp_path, default_rules):
        dest = tmp_path / "out.zip"
        files = list(_walk(tmp_project, default_rules))
        create_backup(tmp_project, files, dest)

        with zipfile.ZipFile(dest) as zf:
            names = {n.replace("\\", "/") for n in zf.namelist()}

        # Structure preserved — 'src/main.py' not 'main.py'
        assert "src/main.py" in names
        assert not any(n == "main.py" for n in names)

    def test_compression_stored(self, tmp_project, tmp_path, default_rules):
        dest = tmp_path / "stored.zip"
        files = list(_walk(tmp_project, default_rules))
        create_backup(tmp_project, files, dest, compression="stored")
        with zipfile.ZipFile(dest) as zf:
            for info in zf.infolist():
                assert info.compress_type == zipfile.ZIP_STORED

    def test_empty_file_list(self, tmp_project, tmp_path):
        dest = tmp_path / "empty.zip"
        create_backup(tmp_project, [], dest)
        assert dest.is_file()
        with zipfile.ZipFile(dest) as zf:
            assert zf.namelist() == []


# ---------------------------------------------------------------------------
# make_destination
# ---------------------------------------------------------------------------

class TestMakeDestination:
    def test_default_goes_to_downloads_backup(self, tmp_project, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        dest = make_destination(tmp_project)
        assert "backup" in str(dest)
        assert dest.parent.name == "backup"

    def test_filename_format(self, tmp_project, tmp_path):
        dest = make_destination(tmp_project, tmp_path)
        # myproject-YYYYMMDD-HHMMSS.zip
        import re
        assert re.match(
            r"myproject-\d{8}-\d{6}\.zip$", dest.name
        ), f"Unexpected filename: {dest.name}"

    def test_custom_backup_dir(self, tmp_project, tmp_path):
        custom = tmp_path / "my_backups"
        dest = make_destination(tmp_project, custom)
        assert dest.parent == custom

    def test_uses_project_name(self, tmp_path):
        project = tmp_path / "coolapp"
        project.mkdir()
        dest = make_destination(project, tmp_path)
        assert dest.name.startswith("coolapp-")


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_minimal_config(self, tmp_path):
        rc = tmp_path / ".backuprc"
        rc.write_text('{"exclude_dirs": ["dist"]}')
        cfg = load_config(rc)
        assert "dist" in cfg.extra_dirs
        assert cfg.include_defaults is True

    def test_full_config(self, tmp_path):
        rc = tmp_path / ".backuprc"
        rc.write_text(json.dumps({
            "exclude_dirs": ["dist", "build"],
            "exclude_names": ["secret.txt"],
            "exclude_extensions": [".bak"],
            "exclude_patterns": [r"\.tmp$"],
            "include_defaults": False,
            "backup_dir": "~/mybackups",
            "compression": "stored",
        }))
        cfg = load_config(rc)
        assert cfg.extra_dirs == ["dist", "build"]
        assert cfg.extra_names == ["secret.txt"]
        assert cfg.extra_extensions == [".bak"]
        assert cfg.extra_patterns == [r"\.tmp$"]
        assert cfg.include_defaults is False
        assert cfg.backup_dir == "~/mybackups"
        assert cfg.compression == "stored"

    def test_invalid_json_raises(self, tmp_path):
        rc = tmp_path / ".backuprc"
        rc.write_text("{not valid json}")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config(rc)

    def test_unknown_compression_defaults_to_deflated(self, tmp_path):
        rc = tmp_path / ".backuprc"
        rc.write_text('{"compression": "superzip9000"}')
        cfg = load_config(rc)
        assert cfg.compression == "deflated"


# ---------------------------------------------------------------------------
# ExclusionRules.build — custom config merging
# ---------------------------------------------------------------------------

class TestExclusionRulesBuild:
    def test_custom_dirs_merged_with_defaults(self):
        cfg = BackupConfig(
            extra_dirs=["my_cache"], extra_names=[], extra_extensions=[],
            extra_patterns=[], include_defaults=True,
            backup_dir=None, compression="deflated",
        )
        rules = ExclusionRules.build(cfg)
        assert "my_cache" in rules.excluded_dirs
        assert ".venv" in rules.excluded_dirs  # default still present

    def test_include_defaults_false(self):
        cfg = BackupConfig(
            extra_dirs=["my_cache"], extra_names=[], extra_extensions=[],
            extra_patterns=[], include_defaults=False,
            backup_dir=None, compression="deflated",
        )
        rules = ExclusionRules.build(cfg)
        assert "my_cache" in rules.excluded_dirs
        assert ".venv" not in rules.excluded_dirs

    def test_extra_extension_without_dot(self):
        cfg = BackupConfig(
            extra_dirs=[], extra_names=[], extra_extensions=["bak"],
            extra_patterns=[], include_defaults=False,
            backup_dir=None, compression="deflated",
        )
        rules = ExclusionRules.build(cfg)
        assert ".bak" in rules.excluded_extensions

    def test_custom_pattern_applied(self, tmp_path):
        (tmp_path / "secret.txt").write_text("top secret")
        cfg = BackupConfig(
            extra_dirs=[], extra_names=[], extra_extensions=[],
            extra_patterns=[r"secret\.txt$"], include_defaults=True,
            backup_dir=None, compression="deflated",
        )
        rules = ExclusionRules.build(cfg)
        files = list(_walk(tmp_path, rules))
        assert not any(f.name == "secret.txt" for f in files)

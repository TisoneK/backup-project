# Full Python Migration

## Overview
Migrate the entire backup project from PowerShell to Python, achieving full cross-platform compatibility, easier distribution, and access to Python's rich ecosystem.

## Requirements

### Complete Migration
- **Core functionality**: Backup logic in Python
- **Cross-platform**: Windows, macOS, Linux support
- **Feature parity**: All current PowerShell features preserved
- **Enhanced capabilities**: Python-specific improvements

### Python Implementation
```python
#!/usr/bin/env python3
import argparse
import zipfile
import json
import sys
from pathlib import Path
from typing import List, Pattern, Set
import re
from datetime import datetime

class BackupProject:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()
        self.exclusions = self.get_default_exclusions()
        self.compression_level = zipfile.ZIP_DEFLATED
    
    def get_default_exclusions(self) -> List[Pattern]:
        patterns = [
            r'\.venv\\',
            r'node_modules\\',
            r'__pycache__\\',
            r'\.git\\',
            r'dist\\',
            r'\.pytest_cache\\',
            r'\.vscode\\',
            r'\.idea\\',
            r'coverage\\',
            r'\.coverage\\',
            r'\.nyc_output\\',
            r'\.next\\',
            r'\.nuxt\\',
            r'\.cache\\',
            r'\.tmp\\',
            r'temp\\',
            r'tmp\\',
            r'logs\\',
            r'\.log\\'
        ]
        return [re.compile(pattern) for pattern in patterns]
    
    def should_exclude(self, file_path: Path) -> bool:
        """Check if file should be excluded based on patterns."""
        for pattern in self.exclusions:
            if pattern.search(str(file_path)):
                return True
        return False
    
    def get_files_to_backup(self) -> List[Path]:
        """Collect all files that should be backed up."""
        files = []
        for file_path in self.project_dir.rglob('*'):
            if file_path.is_file() and not self.should_exclude(file_path):
                files.append(file_path)
        return files
    
    def create_backup(self, destination: Path = None) -> Path:
        """Create the backup archive."""
        if destination is None:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            project_name = self.project_dir.name
            backup_dir = Path.home() / "Downloads" / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            destination = backup_dir / f"{project_name}-{timestamp}.zip"
        
        files = self.get_files_to_backup()
        
        if not files:
            print("No files found after exclusions. Backup not created.")
            return None
        
        print(f"Found {len(files)} files to backup")
        
        with zipfile.ZipFile(destination, 'w', compression=self.compression_level) as zipf:
            for file_path in files:
                # Calculate relative path to preserve directory structure
                arcname = file_path.relative_to(self.project_dir)
                zipf.write(file_path, arcname)
        
        # Display results
        size_mb = destination.stat().st_size / (1024 * 1024)
        print(f"Backup created successfully!")
        print(f"File: {destination}")
        print(f"Size: {size_mb:.2f} MB")
        print(f"Files: {len(files)}")
        
        return destination

def main():
    parser = argparse.ArgumentParser(
        description="Backup a project directory with smart exclusions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  backup_project                    # Backup current directory
  backup_project .                  # Same as above
  backup_project /path/to/project  # Backup specific project
  backup_project --dry-run          # Preview backup without creating
        """
    )
    
    parser.add_argument(
        'project_dir',
        nargs='?',
        default='.',
        help='Path to the project directory to backup (default: current directory)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be backed up without creating the archive'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file (.backuprc)'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        type=str,
        help='Custom output path for the backup file'
    )
    
    args = parser.parse_args()
    
    try:
        backup = BackupProject(args.project_dir)
        
        if args.config:
            backup.load_config(args.config)
        
        if args.dry_run:
            backup.preview_backup()
        else:
            destination = Path(args.output) if args.output else None
            backup.create_backup(destination)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Migration Benefits

### Cross-Platform Compatibility
- **Single codebase** works on Windows, macOS, Linux
- **Native file operations** using Python's pathlib
- **Consistent behavior** across all platforms
- **No execution policy** issues

### Enhanced Features
- **Rich CLI** with argparse (better than PowerShell parameter handling)
- **Configuration management** with JSON/YAML support
- **Plugin system** potential using Python packages
- **Logging and debugging** with Python's logging module

### Distribution Advantages
- **PyPI package**: `pip install backup-project`
- **Standalone executables**: PyInstaller for single-file distribution
- **Docker containers**: Easy containerization
- **GitHub Actions**: Automated testing and releases

### Development Benefits
- **Testing**: pytest ecosystem
- **Type hints**: Better IDE support and error checking
- **Documentation**: Sphinx integration
- **CI/CD**: GitHub Actions, GitLab CI

## Implementation Plan

### Phase 1: Core Migration (Week 1)
- [ ] Basic backup functionality in Python
- [ ] Exclusion pattern matching
- [ ] ZIP creation with directory structure
- [ ] CLI interface with argparse

### Phase 2: Feature Parity (Week 2)
- [ ] Configuration file support (.backuprc)
- [ ] Dry-run mode
- [ ] Progress indicators
- [ ] Error handling improvements

### Phase 3: Enhanced Features (Week 3)
- [ ] Plugin system for custom exclusions
- [ ] Multiple compression formats
- [ ] Cloud storage integration
- [ ] Incremental backups

### Phase 4: Distribution (Week 4)
- [ ] PyPI package setup
- [ ] PyInstaller executables
- [ ] Docker image
- [ ] Documentation and examples

## Migration Strategy

### Backward Compatibility
- **PowerShell wrapper**: Calls Python script for existing users
- **Gradual transition**: Both versions available during migration
- **Migration guide**: Step-by-step instructions for users

### Testing Strategy
- **Unit tests**: pytest for all functions
- **Integration tests**: Cross-platform testing
- **Performance tests**: Compare with PowerShell version
- **Compatibility tests**: Ensure feature parity

### Documentation Migration
- **README updates**: Python installation instructions
- **API docs**: Sphinx-generated documentation
- **Examples**: Python-specific usage examples
- **Migration guide**: PowerShell to Python transition

## Dependencies

### Required Dependencies
```python
# setup.py
install_requires = [
    'pathlib2>=2.3.0; python_version<"3.4"',
    'typing>=3.7.0; python_version<"3.8"',
]

# Optional dependencies
extras_require = {
    'cloud': ['boto3', 'google-cloud-storage'],
    'compression': ['py7zr'],
    'config': ['pyyaml'],
    'progress': ['tqdm'],
}
```

### Development Dependencies
```python
dev_requires = [
    'pytest>=6.0',
    'pytest-cov',
    'black',
    'flake8',
    'mypy',
    'sphinx',
    'sphinx-rtd-theme',
]
```

## Status
📋 **PLANNED** - Specification complete, high-priority migration

## Notes
- This migration addresses execution policy issues completely
- Python packaging enables much easier distribution
- Cross-platform compatibility opens the project to non-Windows users
- Rich Python ecosystem enables advanced features more easily
- Consider maintaining PowerShell version during transition period

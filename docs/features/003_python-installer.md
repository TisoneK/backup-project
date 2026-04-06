# Python Installer Feature

## Overview
Create a Python-based installer that provides cross-platform compatibility and more robust installation handling for the backup project.

## Requirements

### Cross-Platform Support
- **Windows**: Current PowerShell functionality
- **macOS**: Python installer with shell script integration
- **Linux**: Python installer with bash script integration

### Enhanced Installation Features
- **Dependency checking**: Verify PowerShell version and requirements
- **PATH management**: More reliable PATH updates across platforms
- **Rollback capability**: Uninstall or repair installations
- **Configuration management**: Setup default configurations

### Installation Options
```bash
# Basic installation
python install.py

# Custom installation options
python install.py --scripts-dir ~/.local/bin
python install.py --backup-dir ~/backups
python install.py --user-only  # vs system-wide
python install.py --force      # overwrite existing
```

## Implementation Plan

### Phase 1: Basic Python Installer
```python
#!/usr/bin/env python3
import os
import sys
import shutil
import platform
from pathlib import Path

class BackupInstaller:
    def __init__(self):
        self.system = platform.system()
        self.scripts_dir = self.get_default_scripts_dir()
        self.backup_dir = self.get_default_backup_dir()
    
    def get_default_scripts_dir(self):
        if self.system == "Windows":
            return Path.home() / "Scripts"
        else:
            return Path.home() / ".local" / "bin"
    
    def install(self):
        self.check_dependencies()
        self.create_directories()
        self.copy_files()
        self.setup_path()
        self.create_launcher()
```

### Phase 2: Cross-Platform Launchers
- **Windows**: Generate `backup_project.bat` and `backup_project.ps1`
- **macOS/Linux**: Generate `backup_project` shell script
- **Universal**: Python wrapper script option

### Phase 3: Configuration Management
```python
# config.json
{
    "default_backup_dir": "~/backups",
    "default_exclusions": [...],
    "compression_level": "optimal",
    "launcher_type": "native"
}
```

## Benefits

### Cross-Platform Compatibility
- Single installer works everywhere Python is available
- Platform-specific optimizations and integrations
- Consistent user experience across systems

### Enhanced Features
- Better error handling and user feedback
- Dependency verification before installation
- Configuration persistence
- Update and uninstall capabilities

### Developer Experience
- Easier to maintain than multiple platform-specific scripts
- Python's rich ecosystem for file operations
- Better testing capabilities with unittest/pytest

## Migration Strategy

### Phase 1: Coexistence
- Keep PowerShell installer for Windows users
- Add Python installer as alternative option
- Update documentation to show both options

### Phase 2: Primary Installer
- Make Python installer the recommended method
- Maintain PowerShell installer for compatibility
- Add migration guide from PowerShell to Python

### Phase 3: Full Transition
- Python installer becomes primary method
- PowerShell installer deprecated but maintained
- Feature parity achieved

## Technical Considerations

### Dependencies
- Python 3.7+ (for pathlib improvements)
- No external dependencies required
- Uses only Python standard library

### Platform Detection
```python
def detect_platform():
    system = platform.system()
    if system == "Windows":
        return WindowsInstaller()
    elif system == "Darwin":
        return MacOSInstaller()
    elif system == "Linux":
        return LinuxInstaller()
    else:
        raise UnsupportedPlatformError(system)
```

### File Operations
- Use `pathlib.Path` for cross-platform paths
- Handle file permissions appropriately
- Respect user directory standards per platform

## Testing Strategy

### Unit Tests
- Test platform detection
- Test directory creation logic
- Test file copying and permissions

### Integration Tests
- Test installation on each platform
- Test PATH updates
- Test launcher creation

### Manual Testing
- Verify cross-platform compatibility
- Test upgrade scenarios
- Test error conditions

## Status
📋 **PLANNED** - Specification complete, awaiting implementation

## Notes
- Maintain backward compatibility with existing PowerShell installations
- Consider creating a unified installer that detects available tools
- Add verbose mode for debugging installation issues
- Include uninstall functionality for clean removal

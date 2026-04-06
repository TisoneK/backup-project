# Backup Project

A simple PowerShell script to backup any project directory to your Downloads folder, automatically excluding common development directories.

## Features

- 🎯 **Simple usage**: `backup_project` from any directory
- 📁 **Auto-save**: Backups go to `Downloads\backup\{project-name}-{timestamp}.zip`
- 🚫 **Smart exclusions**: Automatically excludes `.venv`, `node_modules`, `__pycache__`, `.git`, etc.
- 🌍 **System-wide**: Install once, use anywhere

## Quick Start

### Installation
```powershell
# Clone or download this project
cd C:\Users\tison\Dev\backup-project
.\install.ps1
```

### Usage
```powershell
# From any directory
backup_project                    # Backup current directory
backup_project .                  # Same as above
backup_project C:\path\to\project # Backup specific project
```

## What Gets Excluded

- Python: `.venv`, `__pycache__`, `.pytest_cache`
- Node.js: `node_modules`, `dist`, `.next`, `.nuxt`
- Git: `.git`
- IDEs: `.vscode`, `.idea`
- Build artifacts: `coverage`, `.coverage`, `.nyc_output`
- Temp files: `.cache`, `.tmp`, `temp`, `tmp`, `logs`, `.log`

## File Structure

```
backup-project/
├── backup_project.ps1    # Main backup script
├── install.ps1           # System-wide installer
└── README.md             # This file
```

## Example Output

```
Starting backup...
Source: C:\Users\tison\Dev\localmind
Destination: C:\Users\tison\Downloads\backup\localmind-20260406-135432.zip
Exclusions: 19 patterns
Found 98 files to backup
Backup created successfully!
File: C:\Users\tison\Downloads\backup\localmind-20260406-135432.zip
Size: 0.12 MB
Files: 98
```

## Installation Details

The installer:
1. Copies scripts to `%USERPROFILE%\Scripts\`
2. Adds the Scripts folder to your user PATH
3. Creates a batch wrapper for easy calling
4. Creates the `Downloads\backup` folder

**Note**: Restart your terminal after installation to use the new PATH.

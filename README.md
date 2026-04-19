# Backup Project

A simple PowerShell script to backup any project directory to your Downloads folder, automatically excluding common development directories.

## Features

- 🎯 **Simple usage**: `backup_project` from any directory
- 📁 **Auto-save**: Backups go to `Downloads\backup\{project-name}-{timestamp}.zip`
- 🚫 **Smart exclusions**: Automatically excludes `.venv`, `node_modules`, `__pycache__`, `.git`, etc.
- 🌍 **System-wide**: Install once, use anywhere
- 🧩 **Modular design**: Clean architecture with reusable utility module

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

### Python
- **Environments**: `.venv`, `env/`, `venv/`
- **Cache**: `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.tox/`, `.nox/`
- **Build**: `build/`, `htmlcov/`, `*.egg-info/`
- **Bytecode**: `*.pyc`, `*.pyo`, `*.pyd`, `*.so`
- **Type checkers**: `.pyre/`, `.pytype/`

### Node.js
- **Dependencies**: `node_modules/`, `bower_components/`, `jspm_packages/`, `web_modules/`
- **Build output**: `dist/`, `.next/`, `.nuxt/`, `.svelte-kit/`, `.vite/`
- **Cache**: `.npm/`, `.eslintcache`, `.stylelintcache`, `.parcel-cache/`
- **Package files**: `*.tgz`, `.yarn-integrity`, `.pnpm-store`, `.pnp.*`

### Environment Files (CRITICAL - contains secrets)
- `.env`, `.env.*`, `.envrc`

### Version Control
- `.git/`

### IDEs & Editors
- `.vscode/`, `.vscode-test/`, `.idea/`, `.spyderproject`, `.ropeproject`

### Testing & Coverage
- `coverage/`, `.coverage*`, `.nyc_output/`

### Build Artifacts & Cache
- `build/`, `.cache/`, `.tmp/`, `temp/`, `tmp/`, `logs/`
- Log files: `*.log`, `*.log.*`

### Windows Specific
- `Thumbs.db`, `ehthumbs.db`, `Desktop.ini`, `$RECYCLE.BIN/`
- Installers: `*.cab`, `*.msi`, `*.msix`, `*.msm`, `*.msp`
- Shortcuts: `*.lnk`, crash dumps: `*.stackdump`

### macOS Specific
- `.DS_Store`, `__MACOSX/`, `.localized`, `._*`
- System directories: `.DocumentRevisions-V100`, `.fseventsd`, `.Spotlight-V100`, `.TemporaryItems`, `.Trashes`

## File Structure

```
backup-project/
├── powershell/
│   ├── backup_project.ps1       # Main backup script (entry point)
│   ├── install.ps1              # System-wide installer
│   └── modules/
│       └── Backup.Utilities.psm1 # Utility functions module
├── tests/
│   └── Backup.Utilities.Tests.ps1 # Unit tests (Pester)
├── docs/
│   ├── plans/
│   │   ├── restructuring-plan.md
│   │   ├── modularization-plan.md
│   │   └── implementation-plan.md
│   └── usage-guide.md           # Detailed usage documentation
├── README.md                    # This file
└── LICENSE                      # (Optional) License file
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
1. Copies main script to `%USERPROFILE%\Scripts\`
2. Adds the Scripts folder to your user PATH
3. Creates a batch wrapper for easy calling
4. Creates the `Downloads\backup` folder

**Note**: Restart your terminal after installation to use the new PATH.

## Development

### Project Organization
The project follows a modular architecture:

- **Main Script** (`powershell/backup_project.ps1`): Orchestrates the backup workflow
- **Utilities Module** (`powershell/modules/Backup.Utilities.psm1`): Reusable functions for:
  - Destination path generation
  - Exclusion pattern management
  - File filtering and collection
  - Archive creation
  - Report formatting

### Testing
Run tests with Pester:
```powershell
Invoke-Pester -Path .\tests\
```

### Module API Documentation
The `Backup.Utilities.psm1` module provides the following functions:

- **Get-BackupDestination**: Generates timestamped backup file paths
- **Get-ExclusionPatterns**: Returns default exclusion pattern array
- **Test-ShouldExclude**: Tests if a file path matches exclusion patterns
- **Get-BackupFiles**: Collects files for backup, filtering exclusions
- **Initialize-BackupDirectory**: Creates backup directory if needed
- **Create-BackupArchive**: Creates ZIP archive with relative paths
- **Write-BackupReport**: Formats and displays backup completion results

### Adding Custom Exclusions
Edit the module file to add custom patterns to the default exclusion list:
```powershell
$defaultExclusions = @(
    '\\\.venv\\',
    # ... existing patterns
    '\\your_custom_pattern\\'
)
```

## Technical Notes

- Uses PowerShell's built-in `Compress-Archive` cmdlet
- Preserves directory structure in ZIP archives
- Regex-based exclusion matching
- Single-threaded file collection (suitable for most projects)
- Compatible with Windows PowerShell 5.1+ and PowerShell 7+

## Roadmap

- [ ] Support for custom exclusion configuration file (`.backuprc`)
- [ ] Incremental backup option
- [ ] Parallel file processing for large projects
- [ ] Dry-run mode to preview what would be backed up
- [ ] Configurable compression level
- [ ] Progress bar for large backups
- [ ] Cloud storage integration (Dropbox, Google Drive, S3)
- [ ] Differential/incremental backup support
- [ ] Backup verification (checksum validation)
- [ ] Multi-project manifest support

## Contributing

1. Follow the plans in `docs/plans/` for major changes
2. Write tests for new functionality
3. Update documentation
4. Ensure all tests pass before submitting changes

## License

MIT License - see LICENSE file for details.
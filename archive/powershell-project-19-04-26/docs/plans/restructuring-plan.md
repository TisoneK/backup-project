# Restructuring Plan

## Overview
Move PowerShell scripts into a dedicated `powershell/` directory to improve project organization and follow best practices for separating code from documentation.

## Current Structure
```
backup-project/
├── backup_project.ps1
├── install.ps1
└── README.md
```

## Proposed Structure
```
backup-project/
├── powershell/
│   ├── backup_project.ps1
│   ├── backup-project.ps1 (symlink/wrapper)
│   ├── install.ps1
│   └── modules/
│       └── Backup.Utilities.psm1
├── docs/
│   ├── plans/
│   │   ├── restructuring-plan.md
│   │   ├── modularization-plan.md
│   │   └── implementation-plan.md
│   └── usage-guide.md
├── tests/
│   ├── backup-project.tests.ps1
│   └── utilities.tests.ps1
├── README.md
├── LICENSE (optional)
└── .gitignore
```

## Changes Required

### 1. Directory Creation
- Create `powershell/` directory
- Create `docs/plans/` directory
- Create `docs/` directory
- Create `tests/` directory

### 2. Move Scripts
- Move `backup_project.ps1` → `powershell/backup_project.ps1`
- Move `install.ps1` → `powershell/install.ps1`

### 3. Maintain Compatibility
- Create wrapper script at project root: `backup-project.ps1` that calls `powershell/backup_project.ps1`
- Update `install.ps1` to handle new paths
- Update README with new paths

### 4. Update README.md
- Update file structure diagram
- Update installation instructions
- Update usage examples (if paths change)
- Add notes about PowerShell execution policy

## Benefits
- Clear separation between code and documentation
- Easier to add tests
- Better organization for future expansion
- Follows conventional project layout
- Allows for proper PowerShell module structure

## Risks
- Breaking changes for existing users
- Need to update install script to handle new paths
- PATH resolution changes for batch wrapper

## Implementation Order
1. Create directory structure
2. Move files
3. Create compatibility wrapper
4. Update paths in install script
5. Update README
6. Test installation and usage
7. Update any CI/CD configurations

## Testing Checklist
- [ ] `backup-project.ps1` works from any directory after install
- [ ] `install.ps1` correctly sets up PATH
- [ ] Backup preserves directory structure
- [ ] All exclusion patterns work correctly
- [ ] Destination folders are created properly
- [ ] Error handling still functional
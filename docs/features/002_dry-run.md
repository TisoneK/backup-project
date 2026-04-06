# Dry-Run Mode

## Overview
Add a dry-run mode that shows what would be backed up without actually creating the ZIP file. This allows users to preview backup contents and exclusions before committing.

## Requirements

### Command Line Option
- **Flag**: `-DryRun` or `-WhatIf`
- **Behavior**: Show preview information, no file creation
- **Compatibility**: Works with all existing parameters

### Preview Information
- Total files that would be backed up
- Total size estimate
- List of excluded files/directories
- Destination path (would-be location)
- Exclusion patterns applied

### Output Format
```
DRY RUN: Backup Preview
========================
Source: C:\Project\MyApp
Destination: C:\Users\User\Downloads\backup\MyApp-20260406-154500.zip

Files to backup: 142
Estimated size: 2.34 MB
Exclusions applied: 19 patterns

Excluded items:
- .venv/ (35 files, 45.2 MB)
- node_modules/ (1,247 files, 156.8 MB)
- .git/ (89 files, 12.1 MB)
- __pycache__/ (23 files, 1.2 MB)

Top included items:
- src/main.py (2.1 KB)
- docs/README.md (4.5 KB)
- config/settings.json (1.2 KB)

Run without -DryRun to create actual backup.
```

## Implementation Plan

### Module Changes
- New function: `Get-BackupPreview`
- Modify main script to support `-DryRun` parameter
- Add size estimation logic
- Create exclusion summary reporting

### Script Changes
```powershell
param(
    [Parameter(Position=0)]
    [string]$ProjectDir = ".",
    
    [Parameter()]
    [switch]$DryRun
)

# In main logic:
if ($DryRun) {
    $preview = Get-BackupPreview -ProjectDir $ProjectDir
    Write-BackupPreview -Preview $preview
    exit 0
}
```

### New Functions
- `Get-BackupPreview` - Collect file statistics without compression
- `Write-BackupPreview` - Format and display preview information
- `Get-ExclusionSummary` - Analyze what was excluded and why

## Testing Strategy

### Unit Tests
- Test preview generation with various project structures
- Test size estimation accuracy
- Test exclusion summary formatting

### Integration Tests
- Test dry-run vs actual backup consistency
- Test with different exclusion patterns
- Test performance on large projects

## Benefits
- **Safety**: Users can verify before backing up
- **Transparency**: Clear view of what's included/excluded
- **Efficiency**: Quick preview without full compression
- **Debugging**: Easy to troubleshoot exclusion rules

## Status
📋 **PLANNED** - Specification complete, awaiting implementation

## Notes
- Should be fast (no compression needed)
- Maintain consistent output format with regular backup
- Consider adding `-Verbose` for more detailed preview

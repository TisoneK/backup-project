# PowerShell Verb Warnings

## Problem
Module functions use unapproved verbs (Initialize, Write, Create). Warning: "names of some imported commands include unapproved verbs."

## Impact
- Cosmetic only - functions work correctly
- No functional impact on backup operations
- May affect discoverability in some PowerShell environments

## Current Functions with Unapproved Verbs
- `Initialize-BackupDirectory` 
- `Write-BackupReport`
- `Create-BackupArchive`

## Solution Plan
Rename functions to use approved PowerShell verbs:
- `Initialize-BackupDirectory` → `New-BackupDirectory`
- `Write-BackupReport` → `Out-BackupReport` 
- `Create-BackupArchive` → `New-BackupArchive`

## Status
⏸️ **LOW PRIORITY** - Cosmetic issue, no functional impact

## Implementation Notes
- Need to update function names in both module and main script
- Update tests to match new function names
- Update documentation to reflect new API
- Consider backward compatibility or breaking change

## Approved PowerShell Verbs Reference
Common approved verbs for file operations:
- `New` - Create new resources
- `Set` - Modify existing resources  
- `Get` - Retrieve data
- `Out` - Output data
- `Remove` - Delete resources

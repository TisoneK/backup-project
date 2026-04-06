# Modularization Plan

## Overview
Break the monolithic `backup_project.ps1` into smaller, reusable functions and potentially a PowerShell module to improve maintainability, testability, and reusability.

## Current State
The main script (~120 lines) combines:
- Path resolution
- Exclusion filtering
- File collection
- Archive creation
- Output/formatting
- Error handling

All logic is in a single procedural script with no clear separation of concerns.

## Proposed Modular Structure

### Module: `Backup.Utilities.psm1`
**Purpose:** Shared utility functions for backup operations

#### Functions to Extract

1. **Get-BackupDestination** (5 lines)
   - Input: `$ProjectDir`, `$BackupDir`
   - Output: Destination path string
   - Logic: Generate timestamped filename

2. **Get-Exclusion Patterns** (3 lines)
   - Input: none (or custom list)
   - Output: Array of regex patterns
   - Logic: Return standard exclusions

3. **Test-ShouldExclude** (5 lines)
   - Input: `$FilePath`, `$Exclusions`
   - Output: Boolean
   - Logic: Check if file matches any exclusion

4. **Get-BackupFiles** (8 lines)
   - Input: `$SourcePath`, `$Exclusions`
   - Output: FileInfo array
   - Logic: Get-ChildItem -Recurse -File, filter exclusions

5. **Initialize-BackupDirectory** (5 lines)
   - Input: `$Destination`
   - Output: None
   - Logic: Create backup directory if missing

6. **Create-BackupArchive** (8 lines)
   - Input: `$Files`, `$SourceDir`, `$Destination`
   - Output: Success boolean
   - Logic: Compress-Archive with relative paths

7. **Write-BackupReport** (10 lines)
   - Input: `$Source`, `$Destination`, `$FileCount`, `$SizeMB`
   - Output: None
   - Logic: Format and display results

### Main Script: `backup_project.ps1` (~40 lines)
**Purpose:** Orchestrate backup workflow

```powershell
param(
    [string]$ProjectDir = "."
)

# Import module
Import-Module "$PSScriptRoot\modules\Backup.Utilities.psm1"

# Resolve paths
$ProjectDir = (Resolve-Path $ProjectDir).Path.TrimEnd('\')
$Destination = Get-BackupDestination $ProjectDir

# Validate, collect files, create archive, report
# (high-level flow only)
```

## Benefits of Modularization

### 1. **Testability** (Priority: High)
- Each function can be unit tested independently
- Mock file system operations easily
- Verify exclusion logic in isolation

### 2. **Reusability** (Priority: High)
- Use same utilities in different backup scripts
- Share module across projects

### 3. **Maintainability** (Priority: Medium)
- Single Responsibility Principle
- Easier to debug specific functions
- Clear function boundaries

### 4. **Extensibility** (Priority: Medium)
- Add new backup types (incremental, differential)
- Support custom exclusions via parameter
- Add compression options

## Implementation Phases

### Phase 1: Extraction (No Breaking Changes)
- Create `Backup.Utilities.psm1`
- Extract functions one at a time
- Keep original script functional during transition
- Add unit tests for each function

### Phase 2: Refactoring
- Rewrite main script to use module
- Remove duplicate code
- Ensure all original functionality preserved

### Phase 3: Enhancement
- Add new features (logging, dry-run, config file)
- Performance improvements
- Parallel file processing

## Testing Strategy

### Unit Tests (Pester)
```powershell
Describe "Get-BackupFiles" {
    It "Filters excluded directories" { }
    It "Includes non-excluded files" { }
}

Describe "Test-ShouldExclude" {
    It "Matches .venv patterns" { }
    It "Matches node_modules patterns" { }
    It "Allows non-matching paths" { }
}
```

### Integration Tests
- Test full backup workflow
- Verify ZIP structure
- Check exclusion accuracy
- Test edge cases (empty dirs, special chars, long paths)

## Acceptance Criteria

- [ ] All original functionality preserved
- [ ] Script passes all tests
- [ ] Code coverage > 80%
- [ ] Backward compatible (same CLI)
- [ ] Documentation updated
- [ ] No performance regression

## Considerations

### PowerShell Module Design
- Use ` Export-ModuleMember` to expose public functions
- Keep private functions internal
- Consider advanced functions with parameter validation

### Error Handling
- Centralize error handling in main script
- Let module functions throw, catch at top level
- Use `-ErrorAction Stop` for critical operations

### Path Handling
- Normalize paths consistently (TrimEnd('\'))
- Use `Join-Path` for path construction
- Handle relative vs absolute paths carefully

## Risks

1. **Breaking Changes**: Incompatible PowerShell versions
   - Mitigation: Test on Windows PowerShell 5.1 and PowerShell 7+

2. **Performance Overhead**: Module import time
   - Mitigation: Negligible for CLI tools

3. **Testing Gap**: Missing edge cases
   - Mitigation: Comprehensive test suite before refactor

## Dependencies
- Pester (for testing) - consider including in tests directory
- PowerShell 5.1+ (for Desired State Configuration support)
# Implementation Plan

## Timeline
- Day 1: Restructuring (move to powershell/ directory)
- Day 2: Modularization (extract functions to module)
- Day 3: Testing and Documentation

## Phase 1: Restructuring (Day 1)

### Step 1.1: Create Directory Structure
```powershell
mkdir powershell
mkdir powershell/modules
mkdir docs/plans
mkdir docs/usage
mkdir tests
```

### Step 1.2: Move Scripts
```powershell
move backup_project.ps1 powershell/
move install.ps1 powershell/
```

### Step 1.3: Create Root Wrapper
Create `backup-project.ps1` at project root:
```powershell
& "$PSScriptRoot\powershell\backup_project.ps1" @args
```

### Step 1.4: Update install.ps1 Impact
- Changes to copy script paths
- Changes to batch wrapper creation
- Update documentation references in install script output

### Step 1.5: Update README
- Correct file structure diagram
- Update installation steps
- Update usage examples

## Phase 2: Modularization (Day 2)

### Step 2.1: Create Module File
- Create `powershell/modules/Backup.Utilities.psm1`
- Define module exports with `Export-ModuleMember`

### Step 2.2: Extract Functions (Order Matters)
1. `Get-BackupDestination` (no dependencies)
2. `Get-ExclusionPatterns` (no dependencies)
3. `Test-ShouldExclude` (uses exclusions)
4. `Get-BackupFiles` (uses Test-ShouldExclude)
5. `Initialize-BackupDirectory` (no dependencies)
6. `Create-BackupArchive` (uses relative paths)
7. `Write-BackupReport` (no dependencies)

### Step 2.3: Update Main Script
- Remove duplicate code
- Import module
- Call functions in sequence
- Keep parameter validation and top-level try/catch

### Step 2.4: Create Pester Tests
- Install Pester if not available
- Create `tests/Backup.Utilities.Tests.ps1`
- Test each function with sample data
- Test edge cases (empty, special chars, long paths)

## Phase 3: Testing & Polish (Day 3)

### Step 3.1: Manual Testing
- Test installation fresh
- Test backup from various directories
- Verify ZIP structure and exclusions
- Test error conditions (missing source, permission denied)

### Step 3.2: Automated Testing
- Run Pester tests
- Achieve >80% code coverage
- Fix any failing tests

### Step 3.3: Documentation Updates
- Update README with new structure info
- Add developer documentation (module API)
- Add troubleshooting section
- Update examples

### Step 3.4: Final Validation
- Restart terminal, test from different directory
- Verify no breaking changes
- Check archive sizes and file counts
- Performance comparison with original

## Task Dependencies

```
Create directories
    ↓
Move scripts
    ↓
Create wrapper
    ↓
Test wrapper works
    ↓
Create module
    ↓
Extract functions (can parallelize)
    ↓
Update main script
    ↓
Write tests (can parallelize with above)
    ↓
Run tests
    ↓
Fix issues
    ↓
Update docs
    ↓
Final integration test
```

## Parallelizable Tasks
- Extract multiple independent functions simultaneously
- Write tests while extracting functions
- Update documentation while testing

## Potential Blockers

1. **PowerShell Execution Policy**
   - Solution: Document how to bypass/set

2. **Pester Version Differences**
   - Solution: Use Pester 5+ syntax, test on both PS 5.1 and 7

3. **Path Edge Cases**
   - Solution: Comprehensive tests for Unicode, spaces, long paths

4. **Compress-Archive Limitations**
   - 4GB limit, long paths (260 char)
   - Solution: Document limitations, consider alternative if needed

## Rollback Plan

If issues arise:
1. Git preserves original files - easy revert
2. Keep original script alongside during transition
3. Wrapper can call either version
4. Document known issues before releasing

## Success Criteria

- [ ] `backup-project` command works from any location
- [ ] ZIP files contain correct directory structure
- [ ] All exclusion patterns function correctly
- [ ] Tests pass with >80% coverage
- [ ] Documentation is accurate and complete
- [ ] No regression in backup speed or reliability
- [ ] Module can be imported independently
- [ ] Clean codebase with clear separation of concerns

## Notes

- Maintain PowerShell 5.1 compatibility (Windows default)
- Consider adding `-WhatIf` and `-Confirm` support
- Investigate using `System.IO.Compression.ZipFile` for better performance/features
- Add progress bar for large backups
- Support for custom exclusion file (.backuprc)

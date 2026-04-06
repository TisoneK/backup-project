# Custom Exclusion Configuration

## Overview
Add support for custom exclusion patterns via configuration files, allowing users to override or extend the default exclusion list.

## Requirements

### Configuration File
- **File name**: `.backuprc` (or `backup.config`)
- **Location**: Project root directory
- **Format**: JSON or simple text format
- **Fallback**: Use default exclusions if config file not found

### Exclusion Patterns
- Support both file and directory patterns
- Glob patterns (e.g., `*.tmp`, `cache/*`)
- Regex patterns for advanced users
- Comments in config file for documentation

## Implementation Plan

### Phase 1: Basic Config Support
```json
{
  "exclusions": [
    "custom-cache/",
    "*.log",
    "temp/*"
  ],
  "includeDefaults": true
}
```

### Phase 2: Advanced Options
```json
{
  "exclusions": [
    "custom-cache/",
    "*.log"
  ],
  "includeDefaults": false,
  "compressionLevel": "Optimal",
  "backupLocation": "custom/path"
}
```

### Module Changes
- New function: `Get-CustomExclusions`
- Modify `Get-ExclusionPatterns` to merge custom + default
- Update `Get-BackupFiles` to use merged exclusions

### Script Changes
- Check for `.backuprc` in project directory
- Load and parse configuration
- Pass custom exclusions to module functions

## Testing Strategy

### Unit Tests
- Test config file loading (missing, invalid, valid)
- Test pattern merging behavior
- Test includeDefaults flag

### Integration Tests
- Test backup with custom exclusions
- Test invalid config handling
- Test performance with large exclusion lists

## Dependencies
- JSON parsing (PowerShell built-in `ConvertFrom-Json`)
- File I/O operations
- Error handling for invalid configs

## Status
📋 **PLANNED** - Specification complete, awaiting implementation

## Notes
- Maintain backward compatibility (no config file = current behavior)
- Consider multiple config file formats (JSON, INI, simple text)
- Add config validation with helpful error messages

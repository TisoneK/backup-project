# Execution Policy Issues

## Problem
`backup_project` command fails with "not digitally signed" error. Scripts blocked by PowerShell execution policy.

## Solution
**Set execution policy permanently (recommended)**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

This is the standard approach for development environments and fixes the issue permanently.

**Alternative: Manual bypass for one-time use**:
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

## Status
🔄 **BLOCKING** - Prevents testing of all other features

## Root Cause
PowerShell execution policy is restrictive by default for security. This affects all unsigned scripts.

## Notes
- This is a one-time setup step for development environments
- RemoteSigned allows local scripts to run without requiring digital signatures
- Affects current user scope only, not system-wide

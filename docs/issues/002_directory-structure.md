# Directory Structure Flattening Bug

## Problem
ZIP files contained all files in root directory, losing folder structure from source project.

## Root Cause
`Compress-Archive` with an array of relative paths always flattens - it doesn't preserve directory structure regardless of how paths are fed to it.

## Solution
Replaced `Compress-Archive` with .NET `ZipFile` API:
- Each file added individually with relative path as entry name
- Preserves original directory structure in ZIP
- Better compression control with `CompressionLevel::Optimal`

## Code Changes
```powershell
# OLD (flattened structure)
Compress-Archive -Path $relativePaths -DestinationPath $Destination -Force

# NEW (preserves structure)
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($Destination, 'Create')
foreach ($file in $Files) {
    $entryName = $file.FullName.Substring($SourceDir.Length + 1)
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $file.FullName, $entryName, [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
}
$zip.Dispose()
```

## Status
🔄 **IMPLEMENTED BUT UNTESTED** - Code fixed with .NET ZipFile API, but needs testing after execution policy is resolved

## Test Plan
1. Resolve execution policy issue
2. Run `backup_project .` on a project with subdirectories
3. Extract ZIP and verify folder structure is preserved
4. Confirm `src/api/models.py` appears as `src/api/models.py` in ZIP, not just `models.py`

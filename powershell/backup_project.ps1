<#
.SYNOPSIS
    Creates a backup archive of a project directory excluding common dev folders.
    
.DESCRIPTION
    Backs up a project directory to a ZIP file while excluding common development
    directories like node_modules, .venv, __pycache__, .git, etc.
    
.PARAMETER ProjectDir
    Path to the project directory to backup. Defaults to current directory.
    
.EXAMPLE
    .\backup_project.ps1
    
.EXAMPLE
    .\backup_project.ps1 .
    
.EXAMPLE
    .\backup_project.ps1 "C:\Users\tison\Dev\localmind"
#>

param(
    [Parameter(Position=0)]
    [string]$ProjectDir = "."
)

# Import the backup utilities module
Import-Module "$PSScriptRoot\modules\Backup.Utilities.psm1" -Force

# Resolve project path to absolute and trim trailing backslash
$ProjectDir = (Resolve-Path $ProjectDir).Path.TrimEnd('\')

# Get destination path and exclusion patterns from module
$Destination = Get-BackupDestination -ProjectDir $ProjectDir
$exclusions = Get-ExclusionPatterns

Write-Host "Starting backup..." -ForegroundColor Green
Write-Host "Source: $ProjectDir" -ForegroundColor Cyan
Write-Host "Destination: $Destination" -ForegroundColor Cyan
Write-Host "Exclusions: $($exclusions.Count) patterns" -ForegroundColor Cyan

# Validate source directory exists
if (-not (Test-Path $ProjectDir -PathType Container)) {
    Write-Error "Source directory does not exist: $ProjectDir"
    exit 1
}

try {
    # Initialize backup directory
    Initialize-BackupDirectory -Destination $Destination
    
    # Get files to backup
    $files = Get-BackupFiles -SourcePath $ProjectDir -Exclusions $exclusions
    $fileCount = ($files | Measure-Object).Count
    Write-Host "Found $fileCount files to backup" -ForegroundColor Yellow

    if ($fileCount -eq 0) {
        Write-Warning "No files found after exclusions. Backup not created."
        exit 0
    }

    # Create the archive
    $archiveCreated = Create-BackupArchive -Files $files -SourceDir $ProjectDir -Destination $Destination
    
    if ($archiveCreated -and (Test-Path $Destination)) {
        $backupSize = (Get-Item $Destination).Length / 1MB
        Write-BackupReport -Source $ProjectDir -Destination $Destination -FileCount $fileCount -SizeMB $backupSize
    } else {
        Write-Error "Backup creation failed - file not found"
        exit 1
    }
}
catch {
    Write-Error "Backup failed: $($_.Exception.Message)"
    exit 1
}

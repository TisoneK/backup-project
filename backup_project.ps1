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

# Resolve project path to absolute
$ProjectDir = Resolve-Path $ProjectDir

# Auto-generate destination: Downloads\{project-name}-{timestamp}.zip
$projectName = Split-Path $ProjectDir -Leaf
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$downloadsPath = [System.Environment]::GetFolderPath('UserProfile') + "\Downloads"
$backupDir = Join-Path $downloadsPath "backup"
$Destination = Join-Path $backupDir "$projectName-$timestamp.zip"

# Default exclusion patterns
$defaultExclusions = @(
    '\\\.venv\\',
    '\\node_modules\\',
    '\\__pycache__\\',
    '\\\.git\\',
    '\\dist\\',
    '\\\.pytest_cache\\',
    '\\\.vscode\\',
    '\\\.idea\\',
    '\\coverage\\',
    '\\\.coverage\\',
    '\\\.nyc_output\\',
    '\\\.next\\',
    '\\\.nuxt\\',
    '\\\.cache\\',
    '\\\.tmp\\',
    '\\temp\\',
    '\\tmp\\',
    '\\logs\\',
    '\\\.log\\'
)

# Combine default exclusions (no custom exclusions supported)
$allExclusions = $defaultExclusions

Write-Host "Starting backup..." -ForegroundColor Green
Write-Host "Source: $ProjectDir" -ForegroundColor Cyan
Write-Host "Destination: $Destination" -ForegroundColor Cyan
Write-Host "Exclusions: $($allExclusions.Count) patterns" -ForegroundColor Cyan

# Validate source directory exists
if (-not (Test-Path $ProjectDir -PathType Container)) {
    Write-Error "Source directory does not exist: $ProjectDir"
    exit 1
}

# Create destination directory if it doesn't exist
$destDir = Split-Path $Destination -Parent
if (-not (Test-Path $destDir)) {
    New-Item -Path $destDir -ItemType Directory -Force | Out-Null
}

try {
    # Get all files and filter out exclusions
    $files = Get-ChildItem -Path $ProjectDir -Recurse -File | Where-Object {
        $filePath = $_.FullName
        # Check if any exclusion pattern matches
        $match = $false
        foreach ($exclusion in $allExclusions) {
            if ($filePath -match $exclusion) {
                $match = $true
                break
            }
        }
        -not $match
    }

    $fileCount = ($files | Measure-Object).Count
    Write-Host "Found $fileCount files to backup" -ForegroundColor Yellow

    if ($fileCount -eq 0) {
        Write-Warning "No files found after exclusions. Backup not created."
        exit 0
    }

    # Create the archive
    $files | Compress-Archive -DestinationPath $Destination -Force
    
    # Verify the backup was created
    if (Test-Path $Destination) {
        $backupSize = (Get-Item $Destination).Length / 1MB
        Write-Host "Backup created successfully!" -ForegroundColor Green
        Write-Host "File: $Destination" -ForegroundColor Cyan
        Write-Host "Size: $([math]::Round($backupSize, 2)) MB" -ForegroundColor Cyan
        Write-Host "Files: $fileCount" -ForegroundColor Cyan
    } else {
        Write-Error "Backup creation failed - file not found"
        exit 1
    }
}
catch {
    Write-Error "Backup failed: $($_.Exception.Message)"
    exit 1
}

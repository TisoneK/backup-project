<#
.SYNOPSIS
    Backup utilities module for project backup operations.

.DESCRIPTION
    Provides reusable functions for creating backup archives with smart exclusions.
    This module extracts core functionality from the main backup script for better
    testability and reusability.
#>

# Function to generate backup destination path
function Get-BackupDestination {
    param(
        [Parameter(Mandatory=$true)]
        [string]$ProjectDir,
        
        [Parameter(Mandatory=$false)]
        [string]$BackupDir = ""
    )
    
    $projectName = Split-Path $ProjectDir -Leaf
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    
    if ([string]::IsNullOrEmpty($BackupDir)) {
        $downloadsPath = [System.Environment]::GetFolderPath('UserProfile') + "\Downloads"
        $BackupDir = Join-Path $downloadsPath "backup"
    }
    
    return Join-Path $BackupDir "$projectName-$timestamp.zip"
}

# Function to get default exclusion patterns
function Get-ExclusionPatterns {
    return @(
        # Python
        '\\\.venv\\',
        '\\__pycache__\\',
        '\\\.pytest_cache\\',
        '\\build\\',
        '\\\.mypy_cache\\',
        '\\\.ruff_cache\\',
        '\\\.tox\\',
        '\\\.nox\\',
        '\\htmlcov\\',
        '\\\.egg-info\\',
        '\\\.pyre\\',
        '\\\.pytype\\',
        
        # Python files
        '\\\.pyc$',
        '\\\.pyo$',
        '\\\.pyd$',
        '\\\.so$',
        
        # Node.js
        '\\node_modules\\',
        '\\dist\\',
        '\\\.next\\',
        '\\\.nuxt\\',
        '\\\.npm\\',
        '\\\.eslintcache',
        '\\\.stylelintcache',
        '\\\.parcel-cache\\',
        '\\\.svelte-kit\\',
        '\\\.vite\\',
        '\\web_modules\\',
        
        # Node.js files
        '\\\.tgz$',
        '\\\.yarn-integrity$',
        '\\\.pnpm-store\\',
        '\\\.pnp\..*$',
        
        # Environment files (CRITICAL - contains secrets)
        '\\\.env$',
        '\\\.env\..*$',
        '\\\.envrc$',
        
        # Git
        '\\\.git\\',
        
        # IDEs
        '\\\.vscode\\',
        '\\\.vscode-test\\',
        '\\\.idea\\',
        '\\\.spyderproject',
        '\\\.ropeproject',
        
        # Coverage and testing
        '\\coverage\\',
        '\\\.coverage',
        '\\\.coverage\..*$',
        '\\\.nyc_output\\',
        
        # Build artifacts
        '\\build\\',
        '\\\.cache\\',
        '\\\.tmp\\',
        '\\temp\\',
        '\\tmp\\',
        '\\logs\\',
        
        # Log files
        '\\\.log$',
        '\\\.log\..*$',
        
        # Windows specific
        'Thumbs\.db',
        'Thumbs\.db:encryptable',
        'ehthumbs\.db',
        'ehthumbs_vista\.db',
        '\\\.stackdump$',
        'Desktop\.ini',
        '\$RECYCLE\.BIN\\',
        '\\\.cab$',
        '\\\.msi$',
        '\\\.msix$',
        '\\\.msm$',
        '\\\.msp$',
        '\\\.lnk$',
        
        # macOS specific
        '\\\.DS_Store$',
        '\\\.localized$',
        '__MACOSX\\',
        '\\\.AppleDouble',
        '\\\.LSOverride',
        'Icon\\[\\r\\n\\]',
        '\\\._.*$',
        '\\\.DocumentRevisions-V100',
        '\\\.fseventsd',
        '\\\.Spotlight-V100',
        '\\\.TemporaryItems',
        '\\\.Trashes',
        '\\\.VolumeIcon\.icns',
        
        # Package managers
        'bower_components\\',
        'jspm_packages\\',
        
        # Misc
        '\\\.cache\\',
        '\\\.tmp\\',
        '\\temp\\',
        '\\tmp\\',
        '\\logs\\',
        '\\\.log$'
    )
}

# Function to test if a file should be excluded
function Test-ShouldExclude {
    param(
        [Parameter(Mandatory=$true)]
        [string]$FilePath,
        
        [Parameter(Mandatory=$true)]
        [string[]]$Exclusions
    )
    
    foreach ($exclusion in $Exclusions) {
        if ($FilePath -match $exclusion) {
            return $true
        }
    }
    return $false
}

# Function to get files for backup
function Get-BackupFiles {
    param(
        [Parameter(Mandatory=$true)]
        [string]$SourcePath,
        
        [Parameter(Mandatory=$true)]
        [string[]]$Exclusions
    )
    
    return Get-ChildItem -Path $SourcePath -Recurse -File | Where-Object {
        -not (Test-ShouldExclude -FilePath $_.FullName -Exclusions $Exclusions)
    }
}

# Function to initialize backup directory
function Initialize-BackupDirectory {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Destination
    )
    
    $destDir = Split-Path $Destination -Parent
    if (-not (Test-Path $destDir)) {
        New-Item -Path $destDir -ItemType Directory -Force | Out-Null
    }
}

# Function to create backup archive
function Create-BackupArchive {
    param(
        [Parameter(Mandatory=$true)]
        [System.IO.FileInfo[]]$Files,
        
        [Parameter(Mandatory=$true)]
        [string]$SourceDir,
        
        [Parameter(Mandatory=$true)]
        [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $zip = $null
    try {
        $zip = [System.IO.Compression.ZipFile]::Open($Destination, 'Create')

        foreach ($file in $Files) {
            # Use relative path as zip entry name — this preserves folder structure
            $entryName = $file.FullName.Substring($SourceDir.Length + 1)
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip,
                $file.FullName,
                $entryName,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }

        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($zip) { $zip.Dispose() }
    }
}

# Function to write backup report
function Write-BackupReport {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Source,
        
        [Parameter(Mandatory=$true)]
        [string]$Destination,
        
        [Parameter(Mandatory=$true)]
        [int]$FileCount,
        
        [Parameter(Mandatory=$false)]
        [double]$SizeMB = 0
    )
    
    Write-Host "Backup created successfully!" -ForegroundColor Green
    Write-Host "File: $Destination" -ForegroundColor Cyan
    Write-Host "Size: $([math]::Round($SizeMB, 2)) MB" -ForegroundColor Cyan
    Write-Host "Files: $FileCount" -ForegroundColor Cyan
}

# Export module members
Export-ModuleMember -Function Get-BackupDestination, Get-ExclusionPatterns, Test-ShouldExclude, Get-BackupFiles, Initialize-BackupDirectory, Create-BackupArchive, Write-BackupReport

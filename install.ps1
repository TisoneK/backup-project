<#
.SYNOPSIS
    Installs backup_project.ps1 system-wide for easy access from any directory.
    
.DESCRIPTION
    Creates a backup directory in Downloads and adds the script to your PATH
    so you can run 'backup_project' from anywhere.
#>

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$scriptPath = Join-Path $scriptDir "backup_project.ps1"

# Create system-wide scripts directory
$scriptsDir = "$env:USERPROFILE\Scripts"
if (-not (Test-Path $scriptsDir)) {
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
    Write-Host "Created scripts directory: $scriptsDir" -ForegroundColor Green
}

# Copy script to system-wide location
$systemScriptPath = Join-Path $scriptsDir "backup_project.ps1"
Copy-Item -Path $scriptPath -Destination $systemScriptPath -Force
Write-Host "Copied script to: $systemScriptPath" -ForegroundColor Green

# Create a batch file wrapper for easier calling
$batchPath = Join-Path $scriptsDir "backup_project.bat"
@"
@echo off
powershell.exe -ExecutionPolicy Bypass -File "%systemScriptPath%" %*
"@ | Out-File -FilePath $batchPath -Encoding ASCII

Write-Host "Created batch wrapper: $batchPath" -ForegroundColor Green

# Add to PATH if not already there
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$scriptsDir*") {
    $newPath = $currentPath + ";$scriptsDir"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $scriptsDir to user PATH" -ForegroundColor Green
    Write-Host "NOTE: Restart your terminal to use the new PATH" -ForegroundColor Yellow
}

Write-Host "`nInstallation complete!" -ForegroundColor Green
Write-Host "You can now run:" -ForegroundColor Cyan
Write-Host "  backup_project                    # from any directory" -ForegroundColor White
Write-Host "  backup_project .                  # current directory" -ForegroundColor White
Write-Host "  backup_project C:\path\to\project # specific project" -ForegroundColor White
Write-Host "`nBackups will be saved to: %USERPROFILE%\Downloads\backup\" -ForegroundColor Cyan

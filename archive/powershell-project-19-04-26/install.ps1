<#
.SYNOPSIS
    Installs backup_project.ps1 system-wide for easy access from any directory.
    
.DESCRIPTION
    Creates a backup directory in Downloads and adds the script to your PATH
    so you can run 'backup_project' from anywhere.
#>

# Call the actual installer
& "$PSScriptRoot\powershell\install.ps1"

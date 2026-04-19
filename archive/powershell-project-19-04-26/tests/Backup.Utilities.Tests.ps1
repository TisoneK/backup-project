# Pester tests for Backup.Utilities module
BeforeAll {
    $ModulePath = Join-Path $PSScriptRoot "..\powershell\modules\Backup.Utilities.psm1"
    Import-Module $ModulePath -Force
}

Describe "Get-BackupDestination" {
    It "Generates destination with default backup directory" {
        $result = Get-BackupDestination -ProjectDir "C:\Test\MyProject"
        $result | Should -Match "backup\\MyProject-\d{8}-\d{6}\.zip$"
    }
    
    It "Uses custom backup directory when provided" {
        $result = Get-BackupDestination -ProjectDir "C:\Test\MyProject" -BackupDir "C:\Custom\Backup"
        $result | Should -Match "C:\\Custom\\Backup\\MyProject-\d{8}-\d{6}\.zip$"
    }
    
    It "Handles project names with spaces" {
        $result = Get-BackupDestination -ProjectDir "C:\Test\My Project"
        $result | Should -Match "backup\\My Project-\d{8}-\d{6}\.zip$"
    }
}

Describe "Get-ExclusionPatterns" {
    It "Returns expected number of exclusion patterns" {
        $patterns = Get-ExclusionPatterns
        $patterns.Count | Should -Be 19
    }
    
    It "Contains common development exclusions" {
        $patterns = Get-ExclusionPatterns
        $patterns | Should -Contain '\\\.venv\\'
        $patterns | Should -Contain '\\node_modules\\'
        $patterns | Should -Contain '\\\.git\\'
        $patterns | Should -Contain '\\__pycache__\\'
    }
}

Describe "Test-ShouldExclude" {
    BeforeEach {
        $exclusions = @('\\\.venv\\', '\\node_modules\\', '\\\.git\\')
    }
    
    It "Excludes .venv directories" {
        $result = Test-ShouldExclude -FilePath "C:\Project\.venv\lib\site-packages\test.py" -Exclusions $exclusions
        $result | Should -Be $true
    }
    
    It "Excludes node_modules directories" {
        $result = Test-ShouldExclude -FilePath "C:\Project\node_modules\react\index.js" -Exclusions $exclusions
        $result | Should -Be $true
    }
    
    It "Excludes .git directories" {
        $result = Test-ShouldExclude -FilePath "C:\Project\.git\config" -Exclusions $exclusions
        $result | Should -Be $true
    }
    
    It "Allows non-excluded files" {
        $result = Test-ShouldExclude -FilePath "C:\Project\src\main.js" -Exclusions $exclusions
        $result | Should -Be $false
    }
    
    It "Handles empty exclusions list" {
        $result = Test-ShouldExclude -FilePath "C:\Project\src\main.js" -Exclusions @()
        $result | Should -Be $false
    }
}

Describe "Initialize-BackupDirectory" {
    It "Creates backup directory when it doesn't exist" {
        $testDest = "C:\Temp\TestBackup\project-20260406-151234.zip"
        $testDir = Split-Path $testDest -Parent
        
        # Ensure directory doesn't exist
        if (Test-Path $testDir) {
            Remove-Item $testDir -Recurse -Force
        }
        
        Initialize-BackupDirectory -Destination $testDest
        
        Test-Path $testDir | Should -Be $true
        
        # Cleanup
        Remove-Item $testDir -Recurse -Force
    }
    
    It "Does not fail when directory already exists" {
        $testDest = "C:\Temp\TestBackup\project-20260406-151234.zip"
        $testDir = Split-Path $testDest -Parent
        
        # Create directory first
        New-Item $testDir -ItemType Directory -Force | Out-Null
        
        { Initialize-BackupDirectory -Destination $testDest } | Should -Not -Throw
        
        # Cleanup
        Remove-Item $testDir -Recurse -Force
    }
}

Describe "Write-BackupReport" {
    It "Writes backup success information" {
        $output = { Write-BackupReport -Source "C:\Test" -Destination "C:\Backup\test.zip" -FileCount 42 -SizeMB 1.5 } | Out-String
        $output | Should -Match "Backup created successfully!"
        $output | Should -Match "Files: 42"
        $output | Should -Match "Size: 1.5 MB"
    }
    
    It "Handles zero size gracefully" {
        { Write-BackupReport -Source "C:\Test" -Destination "C:\Backup\test.zip" -FileCount 0 -SizeMB 0 } | Should -Not -Throw
    }
}

# Integration tests would require actual file system operations
# These are basic unit tests for the module functions

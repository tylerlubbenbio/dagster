# Auto-commit after successful Write/Edit from Cursor
# Works from any directory in the git repository

# Get the current script directory and find git root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$gitRoot = $null

# Try to find git root starting from script directory
$currentPath = $scriptDir
while ($currentPath -ne $null) {
    $gitDir = Join-Path $currentPath ".git"
    if (Test-Path $gitDir) {
        $gitRoot = $currentPath
        break
    }
    $parent = Split-Path -Parent $currentPath
    if ($parent -eq $currentPath) {
        break
    }
    $currentPath = $parent
}

# If not found, try from current working directory
if (-not $gitRoot) {
    $currentPath = Get-Location
    while ($currentPath -ne $null) {
        $gitDir = Join-Path $currentPath ".git"
        if (Test-Path $gitDir) {
            $gitRoot = $currentPath
            break
        }
        $parent = Split-Path -Parent $currentPath
        if ($parent -eq $currentPath) {
            break
        }
        $currentPath = $parent
    }
}

# Exit if not in a git repo
if (-not $gitRoot) {
    exit 0
}

# Change to git root directory
Set-Location $gitRoot

# Check if git is available
try {
    $null = git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0) {
        exit 0
    }
} catch {
    exit 0
}

# Check if there are any uncommitted changes
$hasChanges = $false
try {
    git diff --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        $hasChanges = $true
    }
    
    git diff --cached --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        $hasChanges = $true
    }
} catch {
    exit 0
}

if ($hasChanges) {
    # Build commit message
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $commitMsg = "claude: checkpoint @ $timestamp"
    
    # Stage all changes
    try {
        git add -A 2>$null
        
        # Check if there are staged changes
        git diff --cached --quiet 2>$null
        if ($LASTEXITCODE -eq 0) {
            # No staged changes to commit
            exit 0
        }
        
        # Try to commit
        git commit -m $commitMsg 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Auto-commit: $commitMsg" -ForegroundColor Green
        }
    } catch {
        # Commit may have failed due to git hooks or other reasons
        # That's okay, user can commit manually if needed
    }
}

exit 0

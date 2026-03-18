# Block risky git operations that can delete/lose work

param(
    [string]$InputData = $null
)

# Read from stdin if InputData is not provided
if (-not $InputData) {
    $InputData = $input | Out-String
}

try {
    $json = $InputData | ConvertFrom-Json
    $toolName = $json.tool_name
    
    if ($toolName -ne "Bash") {
        exit 0
    }
    
    $cmd = $json.tool_input.command
    
    if ([string]::IsNullOrWhiteSpace($cmd)) {
        exit 0
    }
    
    # Normalize whitespace
    $cmdNorm = $cmd -replace '\s+', ' '
    
    # Check for risky git commands
    if ($cmdNorm -match '\bgit checkout [^\s]+(\s|$)') {
        Write-Host "❌ BLOCKED: 'git checkout <file>' discards uncommitted changes forever. Use 'git restore <file>' or commit/stash first." -ForegroundColor Red
        exit 2
    }
    
    if ($cmdNorm -match '\bgit reset --hard(\s|$)') {
        Write-Host "❌ BLOCKED: 'git reset --hard' discards ALL uncommitted changes. Use 'git reset --soft' or commit/stash instead." -ForegroundColor Red
        exit 2
    }
    
    if ($cmdNorm -match '\bgit clean -fd(\s|$)') {
        Write-Host "❌ BLOCKED: 'git clean -fd' deletes untracked files. Consider 'git clean -n' to preview, or remove files manually." -ForegroundColor Red
        exit 2
    }
    
    if ($cmdNorm -match '\bgit branch -D(\s|$)') {
        Write-Host "❌ BLOCKED: 'git branch -D' force-deletes branches. Use 'git branch -d' after merging instead." -ForegroundColor Red
        exit 2
    }
    
    if ($cmdNorm -match '\bgit push --force(\s|$)') {
        Write-Host "❌ BLOCKED: 'git push --force' can overwrite remote history. Use 'git push --force-with-lease' with human review instead." -ForegroundColor Red
        exit 2
    }
    
    exit 0
    
} catch {
    Write-Host "Error parsing input: $_" -ForegroundColor Red
    exit 0
}

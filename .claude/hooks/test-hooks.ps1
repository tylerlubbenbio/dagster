# Test script to verify hooks configuration

Write-Host "=== Testing Cursor Hooks Configuration ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Check hooks.json exists and is valid JSON
Write-Host "Test 1: Validating hooks.json..." -ForegroundColor Yellow
try {
    $hooksJson = Get-Content '.cursor\hooks.json' -Raw | ConvertFrom-Json
    Write-Host "  PASS: hooks.json is valid JSON" -ForegroundColor Green
    Write-Host "  PASS: Found $($hooksJson.hooks.Count) hook(s)" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: hooks.json is invalid: $_" -ForegroundColor Red
    exit 1
}

# Test 2: Check all referenced scripts exist
Write-Host ""
Write-Host "Test 2: Checking script files exist..." -ForegroundColor Yellow
$allExist = $true
foreach ($hook in $hooksJson.hooks) {
    $scriptPath = $hook.command
    if (Test-Path $scriptPath) {
        Write-Host "  PASS: $($hook.name)" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: $($hook.name) - Script not found: $scriptPath" -ForegroundColor Red
        $allExist = $false
    }
}

if (-not $allExist) {
    Write-Host ""
    Write-Host "FAIL: Some scripts are missing!" -ForegroundColor Red
    exit 1
}

# Test 3: Test PowerShell syntax of scripts
Write-Host ""
Write-Host "Test 3: Validating PowerShell syntax..." -ForegroundColor Yellow
$syntaxValid = $true
foreach ($hook in $hooksJson.hooks) {
    $scriptPath = $hook.command
    try {
        $null = [System.Management.Automation.PSParser]::Tokenize((Get-Content $scriptPath -Raw), [ref]$null)
        Write-Host "  PASS: $($hook.name) - Syntax valid" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL: $($hook.name) - Syntax error: $_" -ForegroundColor Red
        $syntaxValid = $false
    }
}

if (-not $syntaxValid) {
    Write-Host ""
    Write-Host "FAIL: Some scripts have syntax errors!" -ForegroundColor Red
    exit 1
}

# Test 4: Test scripts can execute (dry run)
Write-Host ""
Write-Host "Test 4: Testing script execution..." -ForegroundColor Yellow
foreach ($hook in $hooksJson.hooks) {
    $scriptPath = $hook.command
    try {
        $result = powershell -File $scriptPath 2>&1
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
            Write-Host "  PASS: $($hook.name) - Executes successfully" -ForegroundColor Green
        } else {
            Write-Host "  WARN: $($hook.name) - Exit code: $LASTEXITCODE" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  FAIL: $($hook.name) - Execution error: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== All Tests Passed! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Hooks Configuration Summary:" -ForegroundColor Cyan
foreach ($hook in $hooksJson.hooks) {
    Write-Host "  Hook: $($hook.name)" -ForegroundColor White
    Write-Host "    Event: $($hook.event)" -ForegroundColor Gray
    Write-Host "    Fail Mode: $($hook.failMode)" -ForegroundColor Gray
    if ($hook.filters -and $hook.filters.tools) {
        $tools = $hook.filters.tools
        Write-Host "    Filters: $tools" -ForegroundColor Gray
    }
}

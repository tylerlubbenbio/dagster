# Debug hook to see what input is being passed
param(
    [string]$InputData = $null
)

# Read from stdin if InputData is not provided
if (-not $InputData) {
    $InputData = $input | Out-String
}

$inputLength = $InputData.Length
Write-Host "DEBUG: Raw input length: $inputLength" -ForegroundColor Yellow

if ($inputLength -gt 0) {
    $preview = if ($inputLength -gt 200) { $InputData.Substring(0, 200) } else { $InputData }
    Write-Host "DEBUG: First 200 chars: $preview" -ForegroundColor Yellow
    
    # Try to parse as JSON
    try {
        $json = $InputData | ConvertFrom-Json
        Write-Host "DEBUG: JSON parsed successfully" -ForegroundColor Green
        Write-Host ($json | ConvertTo-Json -Depth 3 | Select-Object -First 20) -ForegroundColor Cyan
    } catch {
        Write-Host "DEBUG: Not valid JSON or parse failed" -ForegroundColor Red
    }
}

exit 0

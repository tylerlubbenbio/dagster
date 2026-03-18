# Block delete operations; require moving to _ARCHIVED instead

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
    
    # Case 1: explicit Delete tool
    if ($toolName -eq "Delete") {
        Write-Host "❌ BLOCKED: Deleting files is not allowed." -ForegroundColor Red
        Write-Host "Move the file into a _ARCHIVED directory instead (e.g., same folder with /_ARCHIVED/filename)." -ForegroundColor Yellow
        exit 2
    }
    
    # Case 2: Bash rm / unlink / trash via Bash tool
    if ($toolName -eq "Bash") {
        $cmd = $json.tool_input.command
        
        if (-not [string]::IsNullOrWhiteSpace($cmd)) {
            # Check for destructive commands
            if ($cmd -match '\brm\b|\bunlink\b|\btrash\b') {
                Write-Host "❌ BLOCKED: rm/unlink/trash commands are not allowed." -ForegroundColor Red
                Write-Host "Instead of deleting, move files into a _ARCHIVED directory." -ForegroundColor Yellow
                Write-Host "Example: mv path/to/file path/to/_ARCHIVED/file" -ForegroundColor Yellow
                exit 2
            }
        }
    }
    
    exit 0
    
} catch {
    Write-Host "Error parsing input: $_" -ForegroundColor Red
    exit 0
}

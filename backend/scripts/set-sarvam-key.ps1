$ErrorActionPreference = "Stop"

$backendApp = Resolve-Path (Join-Path $PSScriptRoot "..\app")
$envPath = Join-Path $backendApp ".env"

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $backendApp ".env.example") -Destination $envPath
}

$secureKey = Read-Host "Paste your Sarvam API key" -AsSecureString
$keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr)
}

if ([string]::IsNullOrWhiteSpace($key)) {
    throw "Sarvam API key cannot be empty."
}

$lines = Get-Content -LiteralPath $envPath
$updated = $false
$lines = $lines | ForEach-Object {
    if ($_ -match '^SARVAM_API_KEY=') {
        $updated = $true
        "SARVAM_API_KEY=$key"
    } else {
        $_
    }
}

if (-not $updated) {
    $lines += "SARVAM_API_KEY=$key"
}

if (-not ($lines | Where-Object { $_ -match '^SARVAM_CHAT_MODEL=' })) {
    $lines += "SARVAM_CHAT_MODEL=sarvam-30b"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envPath, ($lines -join "`r`n") + "`r`n", $utf8NoBom)

Write-Host "Sarvam key saved to backend/app/.env. Restart the backend server now."


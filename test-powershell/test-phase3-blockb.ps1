# Define the assertion helper function
function Assert-BlockStatus {
    param (
        [string]$Title,
        [string]$Output,
        [int]$ExpectedCode
    )

    # Split on our custom delimiter instead of a newline
    $parts = $Output -split '\|\|\|STATUS\|\|\|'
    $body = $parts[0].Trim()
    $statusCode = [int]($parts[-1].Trim())

    if ($statusCode -eq $ExpectedCode) {
        Write-Host "`n--- $Title -> Status = PASSED (HTTP $statusCode) ---" -ForegroundColor Green
    } else {
        Write-Host "`n--- $Title -> Status = FAILED (Expected: $ExpectedCode, Got: $statusCode) ---" -ForegroundColor Red
    }

    if ($body) {
        Write-Host "Response: $body"
    }
}

# 1. Obtain a fresh client token (not blacklisted in revoked_tokens)
$tokenResponse = curl.exe -s -u "$($env:CLIENT_ID):$($env:CLIENT_SECRET)" -d "grant_type=client_credentials" -d "scope=read:profile:gaming" -d "user_id=$env:USER_ID" "$env:API/oauth/token"
$env:TOKEN = ($tokenResponse | ConvertFrom-Json).access_token

# 2. Update the Authorization header with the new token
$authHeader   = "Authorization: Bearer $($env:TOKEN)"
$originHeader = "Origin: $($env:ORIGIN)"

# 3. Repeat the Phase 3 exit test check (Expected: 403)
$resB = curl.exe -s -w "|||STATUS|||%{http_code}" -H $authHeader -H $originHeader "$($env:API)/users/$($env:USER_ID)/personas/gaming"
Assert-BlockStatus -Title "Phase 3 Exit Test | Read Gaming Persona after UI Revocation" -Output $resB -ExpectedCode 403
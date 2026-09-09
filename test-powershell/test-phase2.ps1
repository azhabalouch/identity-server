Write-Host "`n------------------------------------------"
Write-Host "`n------------ Testing Phase 2 -------------"
Write-Host "`n------------------------------------------"

# ==============================================================================
# Setup: Seed demo data and configure environment variables
# ==============================================================================
$OUT = python manage.py seed_demo$OUT

$env:API = "http://localhost:8000/api/v1"
$env:ORIGIN = "http://localhost:5174"

$env:USER_ID = ($OUT | Where-Object { $_ -match 'user id\s+(\S+)' } | ForEach-Object {$Matches[1] })
$env:CLIENT_ID = ($OUT | Where-Object { $_ -match 'client_id\s+(\S+)' } | ForEach-Object {$Matches[1] })
$env:CLIENT_SECRET = ($OUT | Where-Object { $_ -match 'client_secret\s+(\S+)' } | ForEach-Object {$Matches[1] })

# ==============================================================================
# Block A | Get a gaming token
# ==============================================================================
Write-Host "`n--- Block A | Get a gaming token ---"
$tokenResponse = curl.exe -s -u "$($env:CLIENT_ID):$($env:CLIENT_SECRET)" -d "grant_type=client_credentials" -d "scope=read:profile:gaming" -d "user_id=$env:USER_ID" "$env:API/oauth/token"
$env:TOKEN = ($tokenResponse | ConvertFrom-Json).access_token
$env:TOKEN

# Define reusable headers
$authHeader = "Authorization: Bearer $($env:TOKEN)"
$originHeader = "Origin: $($env:ORIGIN)"

# ==============================================================================
# Block B | Read own persona
# ==============================================================================
Write-Host "`n--- Block B | Read own persona ---"
curl.exe -s -w " %{http_code}`n" -H $authHeader -H $originHeader "$env:API/users/$env:USER_ID/personas/gaming"

# ==============================================================================
# Block C | Read another persona
# ==============================================================================
Write-Host "`n--- Block C | Read another persona ---"
curl.exe -s -w " %{http_code}`n" -H $authHeader -H $originHeader "$env:API/users/$env:USER_ID/personas/professional"

# ==============================================================================
# Block D | Wrong scope format
# ==============================================================================
Write-Host "`n--- Block D | Wrong scope format ---"
curl.exe -s -w " %{http_code}`n" -u "$($env:CLIENT_ID):$($env:CLIENT_SECRET)" -d "grant_type=client_credentials" -d "scope=read:profile:Gaming" -d "user_id=$env:USER_ID" "$env:API/oauth/token"

# ==============================================================================
# Block E | User revokes consent
# ==============================================================================
Write-Host "`n--- Block E | User revokes consent ---"
$loginResponse = curl.exe -s -H "Content-Type: application/json" -H "Origin: http://localhost:5173" -d '{\"email\":\"demo@example.com\",\"password\":\"demo-password-123\"}' "$env:API/auth/login"
$env:SESSION = ($loginResponse | ConvertFrom-Json).access_token

$consentsResponse = curl.exe -s -H "Authorization: Bearer $env:SESSION" "$env:API/consents"
$env:GRANT_ID = (($consentsResponse | ConvertFrom-Json) | Where-Object {$_.persona_context -eq "gaming" } | Select-Object -First 1).id

Write-Host "Revoking grant ID: $env:GRANT_ID"
curl.exe -s -w "%{http_code}`n" -X DELETE -H "Authorization: Bearer $env:SESSION" -H "Origin: http://localhost:5173" "$env:API/consents/$env:GRANT_ID"

Write-Host "`n--- Verify: Try Block B again ---"
curl.exe -s -w " %{http_code}`n" -H $authHeader -H$originHeader "$env:API/users/$env:USER_ID/personas/gaming"

# ==============================================================================
# Block F | User grants again
# ==============================================================================
Write-Host "`n--- Block F | User grants again ---"
curl.exe -s -w " %{http_code}`n" -X POST -H "Authorization: Bearer $env:SESSION" -H "Content-Type: application/json" -H "Origin: http://localhost:5173" -d "{\`"client_id\`":\`"$env:CLIENT_ID\`",\`"persona_context\`":\`"gaming\`"}" "$env:API/consents"

Write-Host "`n--- Verify: Try Block B again ---"
curl.exe -s -w " %{http_code}`n" -H $authHeader -H $originHeader "$env:API/users/$env:USER_ID/personas/gaming"

# ==============================================================================
# Block G | Duplicate email
# ==============================================================================
Write-Host "`n--- Block G | Duplicate email ---"
curl.exe -s -w " %{http_code}`n" -X POST -H "Content-Type: application/json" -d '{\"email\":\"demo@example.com\",\"password\":\"another-password-1\"}' "$env:API/users"

# ==============================================================================
# Block H | Professional key into gaming persona
# ==============================================================================
Write-Host "`n--- Block H | Professional key into gaming persona ---"
curl.exe -s -w " %{http_code}`n" -X PATCH -H "Authorization: Bearer $env:SESSION" -H "Content-Type: application/json" -H "Origin: http://localhost:5173" -d '{\"attributes\":[{\"attribute_key\":\"job_title\",\"attribute_value\":\"x\"}]}' "$env:API/users/$env:USER_ID/personas/gaming"

# ==============================================================================
# Block I | Client revokes its token
# ==============================================================================
Write-Host "`n--- Block I | Client revokes its token ---"
curl.exe -s -w "%{http_code}`n" -u "$($env:CLIENT_ID):$($env:CLIENT_SECRET)" -d "token=$env:TOKEN" "$env:API/oauth/revoke"

Write-Host "`n--- Verify: Try Block B again ---"
curl.exe -s -w " %{http_code}`n" -H $authHeader -H$originHeader "$env:API/users/$env:USER_ID/personas/gaming"
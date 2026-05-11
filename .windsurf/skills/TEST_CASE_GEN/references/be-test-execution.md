# BE Test Execution — API Testing with curl

> Reference document for `TEST_CASE_GEN` skill — EXECUTE mode, Layer 1.
> Defines how AI agent executes API test cases using `run_command` + `curl`.

---

## Tool: `run_command`

All API tests use the `run_command` tool with `curl` commands.

---

## Standard Patterns

### Pattern 1: Simple POST (Login, Register)

```bash
curl -s -w "\n%{http_code}" -X POST {BASE_URL}/api/auth/sessions \
  -H "Content-Type: application/json" \
  -d '{"email":"{EMAIL}","password":"{PASSWORD}"}'
```

**Parse result:**
- Last line = HTTP status code (via `-w "\n%{http_code}"`)
- Everything before last line = response body (JSON)
- Use `-s` for silent mode (no progress bar)

### Pattern 2: Authenticated Request (with JWT)

```bash
curl -s -w "\n%{http_code}" -X GET {BASE_URL}/api/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

### Pattern 3: PUT/PATCH with Body

```bash
curl -s -w "\n%{http_code}" -X PUT {BASE_URL}/api/users/{id} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -d '{"full_name":"Updated Name","role":"ADMIN"}'
```

### Pattern 4: DELETE

```bash
curl -s -w "\n%{http_code}" -X DELETE {BASE_URL}/api/users/{id} \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

### Pattern 5: Rate Limit Test (Burst)

```bash
# Send 6 rapid requests - expect 429 on 6th
for i in $(seq 1 6); do
  echo "--- Attempt $i ---"
  curl -s -w "\n%{http_code}" -X POST {BASE_URL}/api/auth/sessions \
    -H "Content-Type: application/json" \
    -d '{"email":"wrong@test.com","password":"wrong"}'
  echo ""
done
```

### Pattern 6: Security Payload (SQLi/XSS)

```bash
# SQL Injection test
curl -s -w "\n%{http_code}" -X POST {BASE_URL}/api/auth/sessions \
  -H "Content-Type: application/json" \
  -d '{"email":"'\'' OR '\''1'\''='\''1","password":"test"}'

# XSS test
curl -s -w "\n%{http_code}" -X POST {BASE_URL}/api/auth/sessions \
  -H "Content-Type: application/json" \
  -d '{"email":"<script>alert(1)</script>","password":"test"}'
```

### Pattern 7: CORS Test

```bash
curl -s -w "\n%{http_code}" -X OPTIONS {BASE_URL}/api/auth/sessions \
  -H "Origin: http://evil.com" \
  -H "Access-Control-Request-Method: POST"
```

---

## Token Chain Workflow

Many tests require a valid JWT. Use this flow:

```
Step 1: Login → extract token
Step 2: Use token for subsequent requests
```

**Implementation:**

```bash
# Step 1: Login and extract token
RESPONSE=$(curl -s -X POST {BASE_URL}/api/auth/sessions \
  -H "Content-Type: application/json" \
  -d '{"email":"{ADMIN_EMAIL}","password":"{ADMIN_PASSWORD}"}')

# Step 2: Parse token (requires jq or manual parsing)
# If jq available:
TOKEN=$(echo $RESPONSE | jq -r '.token')

# If jq NOT available, use grep:
TOKEN=$(echo $RESPONSE | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

# Step 3: Use token
curl -s -w "\n%{http_code}" -X GET {BASE_URL}/api/users \
  -H "Authorization: Bearer $TOKEN"
```

> **Note:** On Windows PowerShell, use `Invoke-WebRequest` or `curl.exe` instead of `curl` alias.

### PowerShell Alternative

```powershell
# Login
$response = Invoke-RestMethod -Uri "{BASE_URL}/api/auth/sessions" `
  -Method POST -ContentType "application/json" `
  -Body '{"email":"{EMAIL}","password":"{PASSWORD}"}'

$token = $response.token

# Authenticated request
$result = Invoke-RestMethod -Uri "{BASE_URL}/api/users" `
  -Method GET -Headers @{ Authorization = "Bearer $token" }
```

---

## Verification Patterns

### Verify HTTP Status Code

```
Expected: HTTP 200 → Status = PASS if last line = "200"
Expected: HTTP 401 → Status = PASS if last line = "401"
Expected: HTTP 429 → Status = PASS if last line = "429"
```

### Verify Response Body Contains Field

```
Check response contains "token" → grep for '"token"' in response
Check response contains error code → grep for '"code":"INVALID_CREDENTIALS"'
```

### Verify DB State (via Prisma)

```bash
# Check user's last_login_at was updated
npx prisma db execute --stdin <<< "SELECT last_login_at FROM users WHERE email='{EMAIL}'"
```

```powershell
# PowerShell alternative
echo "SELECT last_login_at FROM users WHERE email='{EMAIL}'" | npx prisma db execute --stdin
```

---

## Result Recording

After each curl execution:

| Result                                            | Status    | Actual Column Content                               |
| ------------------------------------------------- | --------- | --------------------------------------------------- |
| HTTP code matches expected, response body matches | `PASS`    | "HTTP {code}, response: {key fields}"               |
| HTTP code wrong                                   | `FAIL`    | "Expected HTTP {x}, got HTTP {y}. Response: {body}" |
| Connection refused / timeout                      | `BLOCKED` | "Server not reachable at {URL}"                     |
| curl not available                                | `BLOCKED` | "curl command not found"                            |

---

## Common Pitfalls

| Issue                                              | Solution                                     |
| -------------------------------------------------- | -------------------------------------------- |
| PowerShell `curl` is alias for `Invoke-WebRequest` | Use `curl.exe` or PowerShell native commands |
| JSON parsing without jq                            | Use `grep` + `cut` pattern shown above       |
| Special characters in password                     | Escape with backslash or use PowerShell      |
| Token expired mid-session                          | Re-login to get fresh token                  |
| Rate limiter triggered                             | Wait 15 minutes or restart server            |

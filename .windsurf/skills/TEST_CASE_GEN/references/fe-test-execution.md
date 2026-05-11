# FE Test Execution — UI Smoke Testing with browser_subagent

> Reference document for `TEST_CASE_GEN` skill — EXECUTE mode, Layer 2.
> Defines how AI agent executes UI smoke tests using `browser_subagent`.

---

## Tool: `browser_subagent`

All FE tests use the `browser_subagent` tool. This tool:
- Opens URLs in an actual browser
- Clicks elements, fills forms, reads text
- Takes screenshots for evidence
- Records as WebP video (automatic)
- Returns observed page state

---

## Scope: Smoke Tests Only

> [!IMPORTANT]
> Layer 2 covers **smoke tests only** — happy path UI flows that verify the page loads, forms submit, and navigation works. NOT for:
> - Full UI regression
> - Visual pixel comparison
> - Dynamic content timing tests
> - Multi-tab/window tests

---

## Standard Patterns

### Pattern 1: Login Flow

```
Task for browser_subagent:
1. Navigate to {FE_URL}/login
2. Wait for page to load
3. Find the email input field and type "{ADMIN_EMAIL}"
4. Find the password input field and type "{ADMIN_PASSWORD}"
5. Click the Login button
6. Wait for navigation to complete
7. Verify the URL is now /dashboard or /admin
8. Verify the page contains a welcome message or user info
9. Return: final URL, any visible user name/email, success/failure
```

### Pattern 2: Form Submit (Create/Edit)

```
Task for browser_subagent:
1. Navigate to {FE_URL}/{PAGE_PATH}
2. Click "Add New" or "Create" button
3. Wait for modal/form to appear
4. Fill in required fields:
   - Field "{FIELD_NAME}": type "{VALUE}"
   - Field "{FIELD_NAME}": type "{VALUE}"
5. Click Submit/Save button
6. Wait for response
7. Verify success message appears OR entry appears in table
8. Return: success/failure, any error messages shown
```

### Pattern 3: Table Verification

```
Task for browser_subagent:
1. Navigate to {FE_URL}/{PAGE_PATH}
2. Wait for table to load
3. Verify the table contains data (not empty)
4. Count the number of rows visible
5. Check if pagination is present
6. Return: row count, pagination status, column headers visible
```

### Pattern 4: Navigation Smoke Test

```
Task for browser_subagent:
1. Navigate to {FE_URL}/login and login with credentials
2. After login, click on sidebar link "{MENU_ITEM}"
3. Verify the page loads without error
4. Verify the page title or header shows "{EXPECTED_TITLE}"
5. Return: page URL, page title, any errors
```

### Pattern 5: Error State Verification

```
Task for browser_subagent:
1. Navigate to {FE_URL}/login
2. Enter WRONG email: "wrong@test.com"
3. Enter WRONG password: "wrongpass"
4. Click Login
5. Verify an error message is displayed
6. Verify the user is NOT redirected (still on /login)
7. Return: error message text, current URL
```

### Pattern 6: Protected Route Test

```
Task for browser_subagent:
1. Open a NEW browser (no previous login)
2. Navigate directly to {FE_URL}/admin/users
3. Verify redirect to /login page
4. Return: final URL (should be /login)
```

---

## Admin-Specific UI Elements

Based on the HealthGuard Admin project structure:

| Page            | URL                     | Key Elements                              |
| --------------- | ----------------------- | ----------------------------------------- |
| Login           | `/login`                | Email input, password input, Login button |
| Dashboard       | `/dashboard`            | Stats cards, welcome message              |
| User Management | `/admin/users`          | UserTable, search bar, "Add User" button  |
| User Form Modal | (modal on /admin/users) | Name, email, role dropdown, Submit        |
| Delete Confirm  | (modal on /admin/users) | Confirm button, Cancel button             |

### Component References (from Project_Structure.md)

| Component    | File                                                   |
| ------------ | ------------------------------------------------------ |
| Login form   | `frontend/src/pages/LoginPage.tsx`                     |
| Admin layout | `frontend/src/components/admin/AdminLayout.tsx`        |
| Sidebar nav  | `frontend/src/components/admin/AdminSidebar.tsx`       |
| User table   | `frontend/src/components/users/UserTable.tsx`          |
| User form    | `frontend/src/components/users/UserFormModal.tsx`      |
| Delete modal | `frontend/src/components/users/DeleteConfirmModal.tsx` |

---

## Evidence Collection

After each browser test:

1. **Screenshot**: browser_subagent automatically records WebP video
2. **Log the final URL** in Actual column
3. **Log visible text** that confirms expected state

### Example Actual Result:

```
URL: /dashboard, displayed: "Welcome, Admin User", sidebar visible with 4 menu items
```

---

## Result Recording

| Browser Observation                        | Status    | Actual Column                                                   |
| ------------------------------------------ | --------- | --------------------------------------------------------------- |
| Page loads, form submits, correct redirect | `PASS`    | "Navigated to /dashboard, user info displayed"                  |
| Form submits but wrong page                | `FAIL`    | "Expected /dashboard, got /login. Error: 'Invalid credentials'" |
| Page shows blank / loading spinner stuck   | `BLOCKED` | "Page did not load. FE server may be down"                      |
| Browser tool error                         | `BLOCKED` | "browser_subagent failed: {error}"                              |

---

## Limitations

| Limitation                            | Workaround                                        |
| ------------------------------------- | ------------------------------------------------- |
| No explicit wait for async render     | Set longer timeout in browser_subagent task       |
| Cannot access localStorage directly   | Verify JWT presence by calling authenticated page |
| Cannot intercept network requests     | Use L1 (curl) for API verification                |
| Cannot test responsive/mobile layouts | Out of scope (L3 manual)                          |
| Cannot do visual regression           | Out of scope (L3 manual)                          |

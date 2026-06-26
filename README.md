# Infodra WorkHub

Microsoft 365 Employee Attendance & Activity Tracker using Microsoft Graph API and SharePoint Online.

## Implemented Modules

### 1) Project Structure
- `backend/`: FastAPI app with service/repository architecture.
- `frontend/`: Next.js 15 App Router UI with MSAL auth.
- `infra/azure/`: deployment and scheduler guidance.

### 2) Microsoft Entra Authentication
- Frontend sign-in with `@azure/msal-browser` and `@azure/msal-react`.
- Backend JWT access-token validation using tenant JWKS and audience checks.
- Role-based authorization for Employee, Manager, Admin.

### 3) Microsoft Graph Integration
Implemented Graph services for:
- User profile
- Sign-in logs
- Presence
- Calendar
- Teams (via presence/activity)
- SharePoint activity
- OneDrive activity
- Organization
- Groups

### 4) SharePoint Integration
SharePoint Online lists are used as storage via Graph list APIs:
- Employees
- Attendance
- ActivityLogs
- Leave
- Holidays
- Settings
- AuditLogs

### 5) Attendance Engine
Attendance auto-calculation with no manual login/logout:
- First Graph activity => Login Time
- Last Graph activity => Logout Time
- Working hours and meeting hours computed
- Status engine supports: Present, Absent, Half Day, Late, On Leave, Holiday, Weekend
- Sync job every 15 minutes using APScheduler

### 6) Dashboard
- Employee Dashboard: login/logout, hours, status, attendance trends
- Manager Dashboard: team present/absent/late, trends
- Admin Dashboard: system health, sync status, reports

### 7) Reports
Report endpoint supports:
- Daily Attendance
- Monthly Attendance
- Late Login
- Working Hours
- Department
- Meeting Hours
- Leave Summary
- Holiday Calendar

### 8) Deployment
- Frontend target: Vercel
- Backend target: Azure App Service
- Scheduler options: APScheduler or Azure Function timer

## SharePoint List Columns

### Employees
- EmployeeID (Single line text)
- EmployeeName (Single line text)
- Email (Single line text)
- Department (Single line text)
- Designation (Single line text)
- Manager (Single line text)
- Status (Choice)
- Location (Single line text)
- JoiningDate (Date)

### Attendance
- Employee (Single line text)
- AttendanceDate (Date)
- LoginTime (DateTime)
- LogoutTime (DateTime)
- WorkingHours (Number)
- MeetingHours (Number)
- AttendanceStatus (Choice)
- Source (Single line text)
- LastActivity (DateTime)
- Remarks (Multiple lines)

### ActivityLogs
- Employee (Single line text)
- ActivityType (Single line text)
- ActivityTime (DateTime)
- Source (Single line text)
- Details (Multiple lines)

### Leave
- Employee (Single line text)
- LeaveType (Choice)
- StartDate (Date)
- EndDate (Date)
- Status (Choice)
- Reason (Multiple lines)

### Holidays
- HolidayName (Single line text)
- HolidayDate (Date)
- Location (Single line text)

### Settings
- OfficeStartTime (Single line text, HH:mm:ss)
- OfficeEndTime (Single line text, HH:mm:ss)
- GracePeriod (Number)
- WorkingHoursPerDay (Number)
- AttendanceCalculationMethod (Single line text)

### AuditLogs
- Action (Single line text)
- Entity (Single line text)
- Details (Multiple lines)
- CreatedAt (DateTime)

## Required Graph Permissions

### Application Permissions
- `AuditLog.Read.All`
- `User.Read.All`
- `Presence.Read.All`
- `Calendars.Read`
- `Mail.Read`
- `Sites.ReadWrite.All`
- `Files.Read.All`
- `Group.Read.All`
- `Organization.Read.All`

Grant admin consent after assigning permissions.

## Run Locally

### Backend
1. Copy `backend/.env.example` to `backend/.env` and fill values.
2. Install dependencies:
   - `pip install -r backend/requirements.txt`
3. Start API:
   - `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### Frontend
1. Copy `frontend/.env.example` to `frontend/.env.local` and fill values.
2. Install dependencies:
   - `npm install`
3. Start app:
   - `npm run dev`

## API Endpoints
- `GET /api/v1/employees`
- `GET /api/v1/attendance/today`
- `GET /api/v1/attendance/month`
- `GET /api/v1/attendance/{employee}`
- `GET /api/v1/dashboard`
- `POST /api/v1/sync`
- `GET /api/v1/reports`
- `GET /api/v1/settings`
- `PUT /api/v1/settings`

## Notes
- Use HTTPS in production (`FORCE_HTTPS=true`).
- Ensure list internal column names match expected payload keys.
- BYOD-compatible: no endpoint agent or browser extension required.


# Employee Management System

A full-stack web application for employee management with role-based authentication, attendance, payroll, leave, and meeting management.

## Features
- Admin & Employee login (role-based)
- Password hashing & session management
- Admin dashboard: KPIs, employee management, payroll, leave approval, meetings
- Employee dashboard: profile, attendance, leave, salary slip, meetings
- Attendance & leave system (with half-day support)
- Salary calculation (PF, ESI, deductions) & PDF slip (ReportLab)
- Responsive, glassmorphism UI (Bootstrap 5, custom CSS)
- MongoDB backend (collections: users, employees, attendance, leaves, salary, meetings)

## Setup
1. Clone repo and install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Start MongoDB (default: mongodb://localhost:27017/employee_mgmt)
3. Run the app:
   ```bash
   python app.py
   ```
4. Open browser at http://127.0.0.1:5000/

## Project Structure
- app.py: Main Flask app
- db.py: MongoDB connection helpers
- auth.py: Authentication logic
- salary.py: Salary logic & PDF
- templates/: HTML templates (Bootstrap, glassmorphism)
- static/: CSS & JS
- docs/mongodb_schema.json: Sample MongoDB schemas

## Sample Data
See docs/mongodb_schema.json for collection structure.

---
*Replace the secret key in production. Extend modules for business logic as needed.*

from flask import Flask
from auth import auth_bp
from db import get_collection, init_db
from salary import send_salary_slip_pdf, store_salary, calculate_salary
from functools import wraps
from datetime import datetime, timedelta
import calendar
from bson import ObjectId

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change in production
app.config['MONGO_URI'] = 'mongodb://localhost:27017/employee_mgmt'

# Initialize MongoDB
init_db(app)

# Register blueprints
app.register_blueprint(auth_bp)

# --- Admin Dashboard, Employee Dashboard, Attendance, Leave, Salary, Meetings ---
# (Stub routes for now, to be implemented in detail)


from flask import render_template, session, redirect, url_for

ROLE_RANK = {
    'employee': 1,
    'manager': 2,
    'hr': 3,
    'admin': 4,
}


def current_role():
    return session.get('role')


def role_at_least(role_name):
    return ROLE_RANK.get(current_role(), 0) >= ROLE_RANK.get(role_name, 0)


def require_role(min_role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not role_at_least(min_role):
                return jsonify({'error': 'Unauthorized'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def log_audit(action, target_type='system', target_id=None, details=None):
    details = details or {}
    get_collection('audit_logs').insert_one({
        'action': action,
        'actor_role': session.get('role'),
        'actor_emp_id': session.get('emp_id'),
        'target_type': target_type,
        'target_id': target_id,
        'details': details,
        'created_on': datetime.now().isoformat(),
    })


def notify_employee(emp_id, title, message, level='info'):
    get_collection('notifications').insert_one({
        'emp_id': emp_id,
        'title': title,
        'message': message,
        'level': level,
        'is_read': False,
        'created_on': datetime.now().isoformat(),
    })


def current_month_window():
    now = datetime.now()
    month_str = now.strftime('%Y-%m')
    first_day = datetime(now.year, now.month, 1).strftime('%Y-%m-%d')
    last_day = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1]).strftime('%Y-%m-%d')
    return month_str, first_day, last_day


def get_leave_policy():
    policy = get_collection('leave_policies').find_one({'is_active': True})
    if policy:
        return policy
    default_policy = {
        'name': 'Default Annual Policy',
        'annual': {'CL': 12, 'SL': 12, 'PL': 18},
        'carry_forward_limit': 10,
        'encashment_rate_per_day': 1000,
        'is_active': True,
        'created_on': datetime.now().isoformat(),
    }
    get_collection('leave_policies').insert_one(default_policy)
    return default_policy


def get_or_create_leave_balance(emp_id, year):
    bal = get_collection('leave_balances').find_one({'emp_id': emp_id, 'year': year})
    if bal:
        return bal
    policy = get_leave_policy()
    annual = policy.get('annual', {})
    bal = {
        'emp_id': emp_id,
        'year': year,
        'CL': float(annual.get('CL', 12)),
        'SL': float(annual.get('SL', 12)),
        'PL': float(annual.get('PL', 18)),
        'used': {'CL': 0.0, 'SL': 0.0, 'PL': 0.0},
        'updated_on': datetime.now().isoformat(),
    }
    get_collection('leave_balances').insert_one(bal)
    return bal

@app.route('/')
def home():
    return render_template(
        'index.html',
        page_title='Welcome',
        auth_title='Welcome',
        auth_subtitle='Access your workspace securely.'
    )

@app.route('/admin/dashboard')
def admin_dashboard():
    if not role_at_least('manager'):
        return redirect(url_for('auth.login'))
    role_name = current_role() or 'admin'
    role_label = role_name.upper()

    department_filter = (request.args.get('department') or '').strip()
    status_filter = (request.args.get('status') or '').strip().lower()
    from_date = (request.args.get('from_date') or '').strip()
    to_date = (request.args.get('to_date') or '').strip()

    employee_query = {}
    if role_name == 'manager' and session.get('emp_id'):
        employee_query['manager_emp_id'] = session.get('emp_id')
    if department_filter:
        employee_query['department'] = department_filter
    if status_filter:
        employee_query['status'] = status_filter

    # KPIs
    employees = list(get_collection('employees').find(employee_query))
    total_employees = len(employees)
    today = datetime.now().strftime('%Y-%m-%d')
    employee_ids = [emp.get('emp_id') for emp in employees if emp.get('emp_id')]

    attendance_query = {'date': today}
    leave_query = {'status': {'$in': ['Pending', 'Pending Manager Approval', 'Pending HR Approval']}}
    if employee_ids:
        attendance_query['emp_id'] = {'$in': employee_ids}
        leave_query['emp_id'] = {'$in': employee_ids}

    if from_date and to_date:
        attendance_query['date'] = {'$gte': from_date, '$lte': to_date}
        leave_query['from_date'] = {'$gte': from_date}
        leave_query['to_date'] = {'$lte': to_date}

    present_today = get_collection('attendance').count_documents(attendance_query)
    pending_leaves = get_collection('leaves').count_documents(leave_query)
    total_payroll = sum(emp.get('salary', 0) for emp in employees)
    # Employee list for table
    employee_rows = [
        {
            'emp_id': emp.get('emp_id'),
            'name': emp.get('name'),
            'department': emp.get('department'),
            'status': emp.get('status', 'active')
        } for emp in employees
    ]
    # Fetch pending leaves
    leave_requests = []
    for leave in get_collection('leaves').find(leave_query).limit(20):
        leave_requests.append({
            'id': str(leave.get('_id')),
            'emp_id': leave.get('emp_id'),
            'from_date': leave.get('from_date'),
            'to_date': leave.get('to_date'),
            'reason': leave.get('reason'),
            'half_day': leave.get('half_day', False),
            'applied_on': leave.get('applied_on', '')
        })
    # Fetch today's attendance records
    attendance_records = []
    for att in get_collection('attendance').find(attendance_query).limit(50):
        attendance_records.append({
            'emp_id': att.get('emp_id'),
            'date': att.get('date'),
            'punch_in': att.get('punch_in', '--'),
            'punch_out': att.get('punch_out', '--'),
            'half_day': att.get('half_day', False)
        })
    available_departments = sorted([d for d in get_collection('employees').distinct('department') if d])

    return render_template(
        'admin_dashboard.html',
        page_title=f'{role_label} Dashboard',
        nav_role=role_name,
        active_nav='dashboard',
        body_class='admin-dashboard-page',
        header_title=f'{role_label} Dashboard',
        header_subtitle='Monitor people operations, payroll visibility, and daily activity.',
        available_departments=available_departments,
        selected_department=department_filter,
        selected_status=status_filter,
        selected_from_date=from_date,
        selected_to_date=to_date,
        kpi_employees=total_employees,
        kpi_present=present_today,
        kpi_leaves=pending_leaves,
        kpi_payroll=total_payroll,
        employee_rows=employee_rows,
        leave_requests=leave_requests,
        attendance_records=attendance_records
    )

@app.route('/employee/dashboard')
def employee_dashboard():
    if session.get('role') != 'employee':
        return redirect(url_for('auth.login'))
    emp_id = session.get('emp_id')
    profile = get_collection('employees').find_one({'emp_id': emp_id})
    from datetime import datetime
    now = datetime.now()
    month_str = now.strftime('%Y-%m')
    # Attendance for this month
    attendance = list(get_collection('attendance').find({'emp_id': emp_id, 'date': {'$regex': f'^{month_str}'}}))
    present_days = len(attendance)
    half_days = sum(1 for a in attendance if a.get('half_day'))
    # Leaves
    leave_count = get_collection('leaves').count_documents({'emp_id': emp_id})
    # Latest salary
    salary = get_collection('salary').find_one({'emp_id': emp_id, 'month': month_str})
    latest_salary = salary['net'] if salary else '--'
    return render_template(
        'employee_dashboard.html',
        page_title='Employee Dashboard',
        nav_role='employee',
        active_nav='dashboard',
        body_class='employee-dashboard-page',
        header_title=f"Welcome, {profile.get('name') if profile else 'Employee'}",
        header_subtitle='Track attendance, leave requests, salary, and announcements in one place.',
        profile=profile,
        present_days=present_days,
        leave_count=leave_count,
        half_days=half_days,
        latest_salary=latest_salary
    )

# API Routes for AJAX

from flask import request, jsonify

@app.route('/api/punch-in', methods=['POST'])
def punch_in():
    if current_role() != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    emp_id = session.get('emp_id')
    today = datetime.now().strftime('%Y-%m-%d')
    # Check if already punched in
    existing = get_collection('attendance').find_one({'emp_id': emp_id, 'date': today})
    if existing and existing.get('punch_in'):
        return jsonify({'error': 'Already punched in'}), 400
    now = datetime.now()
    punch_in_time = now.isoformat()
    policy = get_collection('attendance_policy').find_one({'is_active': True}) or {'shift_start': '09:30', 'grace_minutes': 15}
    shift_start = policy.get('shift_start', '09:30')
    grace_minutes = int(policy.get('grace_minutes', 15))
    shift_dt = datetime.strptime(f"{today} {shift_start}", '%Y-%m-%d %H:%M')
    late_by_mins = max(0, int((now - shift_dt).total_seconds() // 60) - grace_minutes)
    get_collection('attendance').update_one(
        {'emp_id': emp_id, 'date': today},
        {'$set': {'punch_in': punch_in_time, 'late_by_minutes': late_by_mins}},
        upsert=True
    )
    log_audit('attendance_punch_in', 'attendance', f'{emp_id}:{today}', {'late_by_minutes': late_by_mins})
    return jsonify({'success': True, 'punch_in': punch_in_time})

@app.route('/api/punch-out', methods=['POST'])
def punch_out():
    if current_role() != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    emp_id = session.get('emp_id')
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now()
    punch_out_time = now.isoformat()
    attendance_doc = get_collection('attendance').find_one({'emp_id': emp_id, 'date': today}) or {}
    overtime_hours = 0
    if attendance_doc.get('punch_in'):
        try:
            punch_in_dt = datetime.fromisoformat(attendance_doc.get('punch_in'))
            worked_hours = (now - punch_in_dt).total_seconds() / 3600
            overtime_hours = max(0, round(worked_hours - 9, 2))
        except Exception:
            overtime_hours = 0
    get_collection('attendance').update_one(
        {'emp_id': emp_id, 'date': today},
        {'$set': {'punch_out': punch_out_time, 'overtime_hours': overtime_hours}},
        upsert=True
    )
    log_audit('attendance_punch_out', 'attendance', f'{emp_id}:{today}', {'overtime_hours': overtime_hours})
    return jsonify({'success': True, 'punch_out': punch_out_time})

@app.route('/api/apply-leave', methods=['POST'])
def apply_leave():
    if current_role() != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    emp_id = session.get('emp_id')
    data = request.get_json()
    from_date = data.get('from_date')
    to_date = data.get('to_date')
    reason = data.get('reason')
    half_day = data.get('half_day', False)
    leave_type = data.get('leave_type', 'CL').upper()

    if leave_type not in ['CL', 'SL', 'PL']:
        leave_type = 'CL'

    year = datetime.now().year
    balance = get_or_create_leave_balance(emp_id, year)
    available = float(balance.get(leave_type, 0))
    requested_days = 0.5 if half_day else 1.0
    if available < requested_days:
        return jsonify({'error': f'Insufficient {leave_type} balance'}), 400

    employee = get_collection('employees').find_one({'emp_id': emp_id}) or {}
    manager_emp_id = employee.get('manager_emp_id')
    next_status = 'Pending Manager Approval' if manager_emp_id else 'Pending HR Approval'

    leave_doc = {
        'emp_id': emp_id,
        'from_date': from_date,
        'to_date': to_date,
        'reason': reason,
        'leave_type': leave_type,
        'requested_days': requested_days,
        'half_day': half_day,
        'manager_emp_id': manager_emp_id,
        'status': next_status,
        'approval_flow': {
            'manager': {'status': 'pending' if manager_emp_id else 'skipped', 'at': None, 'by': None},
            'hr': {'status': 'pending', 'at': None, 'by': None},
        },
        'applied_on': datetime.now().isoformat(),
    }
    result = get_collection('leaves').insert_one(leave_doc)
    notify_employee(emp_id, 'Leave Request Submitted', f'Your {leave_type} leave request has been submitted.')
    log_audit('leave_applied', 'leave', str(result.inserted_id), {'leave_type': leave_type, 'requested_days': requested_days})
    return jsonify({'success': True, 'leave_id': str(result.inserted_id)})

@app.route('/api/add-employee', methods=['POST'])
def add_employee():
    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    import string, random
    emp_id = 'EMP' + ''.join(random.choices(string.digits, k=4))
    employee_role = data.get('role', 'employee')
    if employee_role not in ['employee', 'manager', 'hr']:
        employee_role = 'employee'

    emp_doc = {
        'emp_id': emp_id,
        'name': data.get('name'),
        'department': data.get('department'),
        'designation': data.get('designation'),
        'phone': data.get('phone'),
        'address': data.get('address'),
        'experience': data.get('experience', 0),
        'salary': data.get('salary', 0),
        'manager_emp_id': data.get('manager_emp_id'),
        'status': 'active',
        'join_date': datetime.now().strftime('%Y-%m-%d'),
        'onboarding': {
            'documents_submitted': False,
            'it_assets_allocated': False,
            'orientation_completed': False,
        }
    }
    get_collection('employees').insert_one(emp_doc)
    from werkzeug.security import generate_password_hash
    user_doc = {
        'emp_id': emp_id,
        'password': generate_password_hash(data.get('password')),
        'role': employee_role
    }
    get_collection('users').insert_one(user_doc)
    get_or_create_leave_balance(emp_id, datetime.now().year)
    notify_employee(emp_id, 'Welcome Onboard', 'Your employee profile is created. Please complete onboarding steps.')
    log_audit('employee_added', 'employee', emp_id, {'role': employee_role})
    return jsonify({'success': True, 'emp_id': emp_id})

@app.route('/api/download-slip', methods=['GET'])
def download_slip():
    if session.get('role') != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    emp_id = session.get('emp_id')
    now = datetime.now()
    month_str = now.strftime('%Y-%m')
    salary = get_collection('salary').find_one({'emp_id': emp_id, 'month': month_str})
    if not salary:
        return jsonify({'error': 'No salary slip for this month'}), 404

    employee = get_collection('employees').find_one({'emp_id': emp_id}) or {}
    base_gross = salary.get('gross', employee.get('salary', 0))
    half_days = salary.get('half_days', 0)
    computed = calculate_salary(base_gross, half_days)

    for key, value in computed.items():
        salary.setdefault(key, value)

    salary.update({
        'name': employee.get('name', ''),
        'department': employee.get('department', ''),
        'designation': employee.get('designation', ''),
    })

    return send_salary_slip_pdf(salary)

@app.route('/api/get-meetings', methods=['GET'])
def get_meetings():
    if current_role() not in ['admin', 'hr', 'manager', 'employee']:
        return jsonify({'error': 'Unauthorized'}), 403
    raw_meetings = list(get_collection('meetings').find().sort('created_on', -1).limit(10))
    meetings = []
    emp_id = session.get('emp_id')
    for m in raw_meetings:
        meetings.append({
            '_id': str(m.get('_id')),
            'title': m.get('title'),
            'message': m.get('message'),
            'created_on': m.get('created_on'),
            'read_by': m.get('read_by', []),
            'is_read': (emp_id in m.get('read_by', [])) if emp_id else False
        })
    return jsonify(meetings)


@app.route('/api/mark-meeting-read/<meeting_id>', methods=['POST'])
def mark_meeting_read(meeting_id):
    if session.get('role') != 'employee':
        return jsonify({'error': 'Unauthorized'}), 403
    from bson import ObjectId
    emp_id = session.get('emp_id')
    try:
        get_collection('meetings').update_one(
            {'_id': ObjectId(meeting_id)},
            {'$addToSet': {'read_by': emp_id}}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/delete-meeting/<meeting_id>', methods=['DELETE'])
def delete_meeting(meeting_id):
    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        get_collection('meetings').delete_one({'_id': ObjectId(meeting_id)})
        log_audit('meeting_deleted', 'meeting', meeting_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/post-meeting', methods=['POST'])
def post_meeting():
    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    meeting_doc = {
        'title': data.get('title'),
        'message': data.get('message'),
        'created_on': datetime.now().isoformat(),
        'read_by': []
    }
    result = get_collection('meetings').insert_one(meeting_doc)
    for emp in get_collection('employees').find({}, {'emp_id': 1}):
        notify_employee(emp.get('emp_id'), 'New Announcement', data.get('title', 'Company update'))
    log_audit('meeting_posted', 'meeting', str(result.inserted_id), {'title': data.get('title')})
    return jsonify({'success': True, 'meeting_id': str(result.inserted_id)})

@app.route('/api/approve-leave/<leave_id>', methods=['POST'])
def approve_leave(leave_id):
    if current_role() not in ['admin', 'hr', 'manager']:
        return jsonify({'error': 'Unauthorized'}), 403

    leave = get_collection('leaves').find_one({'_id': ObjectId(leave_id)})
    if not leave:
        return jsonify({'error': 'Leave request not found'}), 404

    role = current_role()
    update = {}

    if role == 'manager':
        manager_emp_id = leave.get('manager_emp_id')
        if not manager_emp_id or manager_emp_id != session.get('emp_id'):
            return jsonify({'error': 'Manager not assigned for this request'}), 403
        update['status'] = 'Pending HR Approval'
        update['approval_flow.manager'] = {'status': 'approved', 'at': datetime.now().isoformat(), 'by': session.get('emp_id')}
    else:
        update['status'] = 'Approved'
        update['approval_flow.hr'] = {'status': 'approved', 'at': datetime.now().isoformat(), 'by': session.get('emp_id', role)}

        year = datetime.now().year
        emp_id = leave.get('emp_id')
        leave_type = leave.get('leave_type', 'CL')
        requested_days = float(leave.get('requested_days', 0.5 if leave.get('half_day') else 1.0))
        balance = get_or_create_leave_balance(emp_id, year)
        current_available = float(balance.get(leave_type, 0))
        used = float((balance.get('used') or {}).get(leave_type, 0))
        get_collection('leave_balances').update_one(
            {'emp_id': emp_id, 'year': year},
            {'$set': {
                leave_type: max(0, round(current_available - requested_days, 2)),
                f'used.{leave_type}': round(used + requested_days, 2),
                'updated_on': datetime.now().isoformat(),
            }}
        )
        notify_employee(emp_id, 'Leave Approved', f'Your leave request ({leave_type}) has been approved.', 'success')

    get_collection('leaves').update_one({'_id': ObjectId(leave_id)}, {'$set': update})
    log_audit('leave_approved', 'leave', leave_id, {'by_role': role, 'new_status': update.get('status')})
    return jsonify({'success': True, 'status': update.get('status')})

@app.route('/api/reject-leave/<leave_id>', methods=['POST'])
def reject_leave(leave_id):
    if current_role() not in ['admin', 'hr', 'manager']:
        return jsonify({'error': 'Unauthorized'}), 403
    leave = get_collection('leaves').find_one({'_id': ObjectId(leave_id)})
    if not leave:
        return jsonify({'error': 'Leave request not found'}), 404

    role = current_role()
    if role == 'manager':
        manager_emp_id = leave.get('manager_emp_id')
        if manager_emp_id and manager_emp_id != session.get('emp_id'):
            return jsonify({'error': 'Manager not assigned for this request'}), 403

    get_collection('leaves').update_one(
        {'_id': ObjectId(leave_id)},
        {'$set': {
            'status': 'Rejected',
            f'approval_flow.{ "manager" if role == "manager" else "hr" }': {
                'status': 'rejected',
                'at': datetime.now().isoformat(),
                'by': session.get('emp_id', role)
            }
        }}
    )
    notify_employee(leave.get('emp_id'), 'Leave Rejected', 'Your leave request has been rejected.', 'warning')
    log_audit('leave_rejected', 'leave', leave_id, {'by_role': role})
    return jsonify({'success': True})

@app.route('/admin/seed-data')
def seed_data_page():
    if not role_at_least('hr'):
        return redirect(url_for('auth.login'))
    role_name = current_role() or 'admin'
    role_label = role_name.upper()
    return render_template(
        'seed_data.html',
        page_title=f'{role_label} Seed Data',
        nav_role=role_name,
        active_nav='seed',
        body_class='admin-dashboard-page',
        header_title=f'{role_label} Seed Sample Data',
        header_subtitle='Generate test employee records for demos and QA.',
    )


@app.route('/admin/modules')
def admin_modules_page():
    if not role_at_least('manager'):
        return redirect(url_for('auth.login'))
    role_name = current_role() or 'admin'
    role_label = role_name.upper()
    return render_template(
        'admin_modules.html',
        page_title=f'{role_label} Operations',
        nav_role=role_name,
        active_nav='operations',
        body_class='admin-dashboard-page',
        header_title=f'{role_label} Operations',
        header_subtitle='Reports, policies, lifecycle, role management, and compliance controls.',
    )


@app.route('/employee/modules')
def employee_modules_page():
    if current_role() != 'employee':
        return redirect(url_for('auth.login'))
    return render_template(
        'employee_modules.html',
        page_title='Employee Services',
        nav_role='employee',
        active_nav='services',
        body_class='employee-dashboard-page',
        header_title='Employee Services',
        header_subtitle='Self-service hub for profile, attendance insights, notifications, and reimbursements.',
    )

@app.route('/api/seed-employees', methods=['POST'])
def seed_employees():
    """Seed 50 sample employees for testing"""
    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    import random
    from werkzeug.security import generate_password_hash
    
    first_names = ['John', 'Sarah', 'Michael', 'Emma', 'David', 'Jessica', 'Robert', 'Lisa', 'James', 'Maria', 
                   'William', 'Patricia', 'Richard', 'Jennifer', 'Thomas', 'Linda', 'Charles', 'Barbara', 'Christopher', 'Karen',
                   'Daniel', 'Nancy', 'Matthew', 'Sandra', 'Anthony', 'Donna', 'Mark', 'Carol', 'Donald', 'Shirley']
    
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                  'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']
    
    departments = ['IT', 'HR', 'Sales', 'Finance', 'Marketing', 'Operations', 'Support', 'Legal', 'R&D', 'Admin']
    
    designations = ['Developer', 'Manager', 'Executive', 'Analyst', 'Engineer', 'Coordinator', 'Specialist', 'Officer', 'Lead', 'Associate']
    
    addresses = ['123 Main St', '456 Oak Ave', '789 Pine Rd', '321 Elm Ave', '654 Maple St', '987 Cedar Ln', '111 Birch Dr', 
                 '222 Spruce Rd', '333 Ash St', '444 Willow Ave']
    
    phone_base = '98765432'
    
    added_count = 0
    
    for i in range(50):
        emp_id = f'EMP{1000 + i}'
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        name = f'{first_name} {last_name}'
        
        # Check if employee already exists
        if get_collection('employees').find_one({'emp_id': emp_id}):
            continue
        
        emp_doc = {
            'emp_id': emp_id,
            'name': name,
            'department': random.choice(departments),
            'designation': random.choice(designations),
            'phone': f'{phone_base}{random.randint(11, 99)}',
            'address': f'{random.randint(100, 999)} {random.choice(addresses)}',
            'experience': random.randint(0, 15),
            'salary': random.choice([25000, 30000, 35000, 40000, 45000, 50000, 55000, 60000, 75000, 100000]),
            'status': 'active'
        }
        
        get_collection('employees').insert_one(emp_doc)
        
        # Create user account for employee
        assigned_role = 'employee'
        if i % 20 == 0:
            assigned_role = 'manager'
        elif i % 33 == 0:
            assigned_role = 'hr'

        user_doc = {
            'emp_id': emp_id,
            'password': generate_password_hash('password123'),
            'role': assigned_role
        }
        get_collection('users').insert_one(user_doc)
        get_or_create_leave_balance(emp_id, datetime.now().year)
        
        added_count += 1
    
    log_audit('seed_employees', 'system', 'seed', {'count': added_count})
    return jsonify({'success': True, 'message': f'{added_count} employees added successfully!'})


@app.route('/api/profile', methods=['GET', 'PUT'])
@require_role('employee')
def profile_self_service():
    emp_id = session.get('emp_id')
    if request.method == 'GET':
        profile = get_collection('employees').find_one({'emp_id': emp_id}, {'_id': 0})
        return jsonify(profile or {})

    data = request.get_json() or {}
    allowed = {
        'phone': data.get('phone'),
        'address': data.get('address'),
    }
    update_doc = {k: v for k, v in allowed.items() if v is not None}
    if not update_doc:
        return jsonify({'error': 'No updatable fields provided'}), 400
    update_doc['updated_on'] = datetime.now().isoformat()
    get_collection('employees').update_one({'emp_id': emp_id}, {'$set': update_doc})
    log_audit('profile_updated', 'employee', emp_id, {'fields': list(update_doc.keys())})
    return jsonify({'success': True})


@app.route('/api/notifications', methods=['GET'])
@require_role('employee')
def get_notifications():
    emp_id = session.get('emp_id')
    docs = list(get_collection('notifications').find({'emp_id': emp_id}).sort('created_on', -1).limit(50))
    result = []
    for d in docs:
        result.append({
            'id': str(d.get('_id')),
            'title': d.get('title'),
            'message': d.get('message'),
            'level': d.get('level', 'info'),
            'is_read': d.get('is_read', False),
            'created_on': d.get('created_on'),
        })
    return jsonify(result)


@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
@require_role('employee')
def mark_notification_read(notification_id):
    emp_id = session.get('emp_id')
    get_collection('notifications').update_one(
        {'_id': ObjectId(notification_id), 'emp_id': emp_id},
        {'$set': {'is_read': True, 'read_on': datetime.now().isoformat()}}
    )
    return jsonify({'success': True})


@app.route('/api/leave-balance', methods=['GET'])
@require_role('employee')
def leave_balance():
    emp_id = session.get('emp_id')
    year = int(request.args.get('year', datetime.now().year))
    bal = get_or_create_leave_balance(emp_id, year)
    bal.pop('_id', None)
    return jsonify(bal)


@app.route('/api/leave-history', methods=['GET'])
@require_role('employee')
def leave_history():
    emp_id = session.get('emp_id')
    leaves = list(get_collection('leaves').find({'emp_id': emp_id}).sort('applied_on', -1).limit(100))
    result = []
    for l in leaves:
        result.append({
            'id': str(l.get('_id')),
            'from_date': l.get('from_date'),
            'to_date': l.get('to_date'),
            'leave_type': l.get('leave_type', 'CL'),
            'status': l.get('status'),
            'requested_days': l.get('requested_days'),
            'applied_on': l.get('applied_on'),
        })
    return jsonify(result)


@app.route('/api/attendance/summary', methods=['GET'])
@require_role('employee')
def attendance_summary():
    emp_id = session.get('emp_id')
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    records = list(get_collection('attendance').find({'emp_id': emp_id, 'date': {'$regex': f'^{month_str}'}}))
    present = len(records)
    half_days = sum(1 for r in records if r.get('half_day'))
    late_marks = sum(1 for r in records if (r.get('late_by_minutes') or 0) > 0)
    overtime_hours = round(sum(float(r.get('overtime_hours', 0) or 0) for r in records), 2)
    return jsonify({
        'month': month_str,
        'present_days': present,
        'half_days': half_days,
        'late_marks': late_marks,
        'overtime_hours': overtime_hours,
    })


@app.route('/api/policy/attendance', methods=['GET', 'PUT'])
def attendance_policy():
    if request.method == 'GET':
        return jsonify(get_collection('attendance_policy').find_one({'is_active': True}, {'_id': 0}) or {
            'shift_start': '09:30',
            'shift_end': '18:30',
            'grace_minutes': 15,
            'weekly_off': ['Saturday', 'Sunday'],
        })

    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    data['is_active'] = True
    data['updated_on'] = datetime.now().isoformat()
    get_collection('attendance_policy').update_many({}, {'$set': {'is_active': False}})
    get_collection('attendance_policy').insert_one(data)
    log_audit('attendance_policy_updated', 'policy', 'attendance', data)
    return jsonify({'success': True})


@app.route('/api/policy/leave', methods=['GET', 'PUT'])
def leave_policy():
    if request.method == 'GET':
        pol = get_leave_policy()
        pol.pop('_id', None)
        return jsonify(pol)

    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    payload = {
        'name': data.get('name', 'Company Leave Policy'),
        'annual': data.get('annual', {'CL': 12, 'SL': 12, 'PL': 18}),
        'carry_forward_limit': data.get('carry_forward_limit', 10),
        'encashment_rate_per_day': data.get('encashment_rate_per_day', 1000),
        'is_active': True,
        'updated_on': datetime.now().isoformat(),
    }
    get_collection('leave_policies').update_many({}, {'$set': {'is_active': False}})
    get_collection('leave_policies').insert_one(payload)
    log_audit('leave_policy_updated', 'policy', 'leave', payload)
    return jsonify({'success': True})


@app.route('/api/holidays', methods=['GET', 'POST'])
def holidays():
    if request.method == 'GET':
        year = request.args.get('year')
        query = {'year': int(year)} if year else {}
        docs = list(get_collection('holidays').find(query).sort('date', 1))
        return jsonify([{'id': str(h['_id']), 'date': h.get('date'), 'name': h.get('name'), 'year': h.get('year')} for h in docs])

    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    holiday = {
        'date': data.get('date'),
        'name': data.get('name'),
        'year': int((data.get('date') or datetime.now().strftime('%Y'))[:4]),
        'created_on': datetime.now().isoformat(),
    }
    result = get_collection('holidays').insert_one(holiday)
    log_audit('holiday_added', 'holiday', str(result.inserted_id), holiday)
    return jsonify({'success': True, 'id': str(result.inserted_id)})


@app.route('/api/shifts', methods=['GET', 'POST'])
def shifts():
    if request.method == 'GET':
        docs = list(get_collection('shifts').find().sort('name', 1))
        return jsonify([{'id': str(s['_id']), 'name': s.get('name'), 'start': s.get('start'), 'end': s.get('end')} for s in docs])

    if not role_at_least('hr'):
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    shift = {
        'name': data.get('name', 'General Shift'),
        'start': data.get('start', '09:30'),
        'end': data.get('end', '18:30'),
        'created_on': datetime.now().isoformat(),
    }
    result = get_collection('shifts').insert_one(shift)
    log_audit('shift_added', 'shift', str(result.inserted_id), shift)
    return jsonify({'success': True, 'id': str(result.inserted_id)})


@app.route('/api/expenses', methods=['GET', 'POST'])
@require_role('employee')
def expenses():
    emp_id = session.get('emp_id')
    if request.method == 'GET':
        query = {'emp_id': emp_id}
        if role_at_least('hr'):
            query = {}
        docs = list(get_collection('expenses').find(query).sort('created_on', -1).limit(200))
        return jsonify([{
            'id': str(d['_id']),
            'emp_id': d.get('emp_id'),
            'category': d.get('category'),
            'amount': d.get('amount'),
            'status': d.get('status'),
            'submitted_on': d.get('created_on'),
        } for d in docs])

    data = request.get_json() or {}
    expense = {
        'emp_id': emp_id,
        'category': data.get('category', 'Travel'),
        'amount': float(data.get('amount', 0)),
        'description': data.get('description', ''),
        'status': 'Pending',
        'created_on': datetime.now().isoformat(),
    }
    result = get_collection('expenses').insert_one(expense)
    notify_employee(emp_id, 'Expense Submitted', 'Your reimbursement request is submitted.')
    log_audit('expense_submitted', 'expense', str(result.inserted_id), expense)
    return jsonify({'success': True, 'id': str(result.inserted_id)})


@app.route('/api/expenses/<expense_id>/approve', methods=['POST'])
@require_role('hr')
def approve_expense(expense_id):
    get_collection('expenses').update_one(
        {'_id': ObjectId(expense_id)},
        {'$set': {'status': 'Approved', 'approved_on': datetime.now().isoformat(), 'approved_by': session.get('emp_id', current_role())}}
    )
    expense = get_collection('expenses').find_one({'_id': ObjectId(expense_id)})
    if expense:
        notify_employee(expense.get('emp_id'), 'Expense Approved', f"Your expense claim ({expense.get('category')}) has been approved.", 'success')
    log_audit('expense_approved', 'expense', expense_id)
    return jsonify({'success': True})


@app.route('/api/onboarding/<emp_id>', methods=['GET', 'PUT'])
@require_role('hr')
def onboarding(emp_id):
    if request.method == 'GET':
        emp = get_collection('employees').find_one({'emp_id': emp_id}, {'_id': 0, 'name': 1, 'emp_id': 1, 'onboarding': 1})
        return jsonify(emp or {})

    data = request.get_json() or {}
    onboarding_update = {
        'onboarding.documents_submitted': bool(data.get('documents_submitted', False)),
        'onboarding.it_assets_allocated': bool(data.get('it_assets_allocated', False)),
        'onboarding.orientation_completed': bool(data.get('orientation_completed', False)),
        'onboarding.updated_on': datetime.now().isoformat(),
    }
    get_collection('employees').update_one({'emp_id': emp_id}, {'$set': onboarding_update})
    log_audit('onboarding_updated', 'employee', emp_id, onboarding_update)
    return jsonify({'success': True})


@app.route('/api/offboarding/initiate/<emp_id>', methods=['POST'])
@require_role('hr')
def initiate_offboarding(emp_id):
    data = request.get_json() or {}
    get_collection('offboarding').insert_one({
        'emp_id': emp_id,
        'reason': data.get('reason', 'Resignation'),
        'last_working_day': data.get('last_working_day'),
        'asset_return': {'laptop': False, 'id_card': False, 'sim': False},
        'fnf_status': 'Pending',
        'status': 'In Progress',
        'created_on': datetime.now().isoformat(),
    })
    get_collection('employees').update_one({'emp_id': emp_id}, {'$set': {'status': 'offboarding'}})
    notify_employee(emp_id, 'Offboarding Initiated', 'Please complete your exit checklist.', 'warning')
    log_audit('offboarding_initiated', 'employee', emp_id, data)
    return jsonify({'success': True})


@app.route('/api/reports/overview', methods=['GET'])
@require_role('hr')
def report_overview():
    month_str, first_day, last_day = current_month_window()
    total_employees = get_collection('employees').count_documents({'status': {'$in': ['active', 'offboarding']}})
    active_employees = get_collection('employees').count_documents({'status': 'active'})
    on_leave = get_collection('leaves').count_documents({
        'status': 'Approved',
        'from_date': {'$lte': last_day},
        'to_date': {'$gte': first_day},
    })
    payroll_docs = list(get_collection('salary').find({'month': month_str}))
    payroll_total = round(sum(float(p.get('net', 0) or 0) for p in payroll_docs), 2)
    return jsonify({
        'month': month_str,
        'headcount_total': total_employees,
        'headcount_active': active_employees,
        'currently_on_leave': on_leave,
        'payroll_total_net': payroll_total,
    })


@app.route('/api/reports/attendance', methods=['GET'])
@require_role('hr')
def report_attendance():
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    pipeline = [
        {'$match': {'date': {'$regex': f'^{month_str}'}}},
        {'$group': {
            '_id': '$emp_id',
            'present_days': {'$sum': 1},
            'late_marks': {'$sum': {'$cond': [{'$gt': ['$late_by_minutes', 0]}, 1, 0]}},
            'overtime_hours': {'$sum': {'$ifNull': ['$overtime_hours', 0]}},
        }},
        {'$sort': {'_id': 1}}
    ]
    rows = list(get_collection('attendance').aggregate(pipeline))
    for r in rows:
        r['emp_id'] = r.pop('_id')
    return jsonify(rows)


@app.route('/api/reports/payroll', methods=['GET'])
@require_role('hr')
def report_payroll():
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    docs = list(get_collection('salary').find({'month': month_str}))
    rows = []
    for d in docs:
        rows.append({
            'emp_id': d.get('emp_id'),
            'gross': d.get('gross', 0),
            'deductions': d.get('total_deductions', d.get('pf', 0) + d.get('esi', 0) + d.get('deductions', 0)),
            'net': d.get('net', 0),
        })
    return jsonify({'month': month_str, 'rows': rows})


@app.route('/api/reports/attrition', methods=['GET'])
@require_role('hr')
def report_attrition():
    total = get_collection('employees').count_documents({})
    exited = get_collection('employees').count_documents({'status': {'$in': ['inactive', 'offboarded']}})
    attrition_rate = round((exited / total * 100), 2) if total else 0
    return jsonify({'total_employees': total, 'exited_employees': exited, 'attrition_rate_percent': attrition_rate})


@app.route('/api/audit-logs', methods=['GET'])
@require_role('admin')
def audit_logs():
    docs = list(get_collection('audit_logs').find().sort('created_on', -1).limit(200))
    response = []
    for d in docs:
        response.append({
            'id': str(d.get('_id')),
            'action': d.get('action'),
            'actor_role': d.get('actor_role'),
            'actor_emp_id': d.get('actor_emp_id'),
            'target_type': d.get('target_type'),
            'target_id': d.get('target_id'),
            'details': d.get('details'),
            'created_on': d.get('created_on'),
        })
    return jsonify(response)


@app.route('/api/admin/create-user', methods=['POST'])
@require_role('admin')
def admin_create_user():
    data = request.get_json() or {}
    from werkzeug.security import generate_password_hash

    role = data.get('role', 'employee')
    if role not in ['employee', 'manager', 'hr', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400

    if role == 'admin':
        username = data.get('username')
        if not username:
            return jsonify({'error': 'username required for admin'}), 400
        if get_collection('users').find_one({'username': username, 'role': 'admin'}):
            return jsonify({'error': 'Admin username already exists'}), 400
        get_collection('users').insert_one({
            'username': username,
            'password': generate_password_hash(data.get('password', 'admin@123')),
            'role': 'admin'
        })
        log_audit('admin_user_created', 'user', username, {'role': role})
        return jsonify({'success': True, 'username': username})

    emp_id = data.get('emp_id')
    if not emp_id:
        return jsonify({'error': 'emp_id required'}), 400
    user = get_collection('users').find_one({'emp_id': emp_id})
    if user:
        get_collection('users').update_one({'emp_id': emp_id}, {'$set': {'role': role}})
    else:
        get_collection('users').insert_one({
            'emp_id': emp_id,
            'password': generate_password_hash(data.get('password', 'password123')),
            'role': role
        })
    log_audit('employee_role_assigned', 'user', emp_id, {'role': role})
    return jsonify({'success': True, 'emp_id': emp_id, 'role': role})


@app.route('/api/download-slip/<emp_id>/<month_str>', methods=['GET'])
@require_role('hr')
def download_slip_for_admin(emp_id, month_str):
    salary = get_collection('salary').find_one({'emp_id': emp_id, 'month': month_str})
    if not salary:
        return jsonify({'error': 'Salary slip not found'}), 404

    employee = get_collection('employees').find_one({'emp_id': emp_id}) or {}
    computed = calculate_salary(salary.get('gross', employee.get('salary', 0)), salary.get('half_days', 0))
    for key, value in computed.items():
        salary.setdefault(key, value)
    salary.update({
        'name': employee.get('name', ''),
        'department': employee.get('department', ''),
        'designation': employee.get('designation', ''),
        'month': month_str,
        'emp_id': emp_id,
    })
    return send_salary_slip_pdf(salary)

if __name__ == '__main__':
    app.run(debug=True)

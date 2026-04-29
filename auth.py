

from flask import Blueprint, request, session, redirect, url_for, flash, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_collection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('emp_id')
        password = request.form['password']
        selected_role = request.form.get('role', 'employee')

        if selected_role in ['admin', 'hr', 'manager']:
            query = {'role': selected_role}
            if selected_role == 'admin':
                query['username'] = username
            else:
                query['emp_id'] = username
            user = get_collection('users').find_one(query)
            if user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session['role'] = selected_role
                if selected_role in ['hr', 'manager']:
                    session['emp_id'] = username
                flash(f'{selected_role.capitalize()} login successful!')
                return redirect(url_for('admin_dashboard'))
            flash(f'Invalid {selected_role} credentials!')
        else:
            emp = get_collection('employees').find_one({'emp_id': username})
            user = get_collection('users').find_one({'role': 'employee', 'emp_id': username})
            if emp and user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session['role'] = 'employee'
                session['emp_id'] = emp['emp_id']
                flash('Employee login successful!')
                return redirect(url_for('employee_dashboard'))
            flash('Invalid employee credentials!')
    return render_template(
        'login.html',
        page_title='Sign In',
        auth_title='Sign In',
        auth_subtitle='Access your dashboard securely.',
        body_class='login-page login-role-employee'
    )

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out!')
    return redirect(url_for('auth.login'))

@auth_bp.route('/admin_signup', methods=['GET', 'POST'])
def admin_signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if get_collection('users').find_one({'username': username, 'role': 'admin'}):
            flash('Admin username already exists!')
            return redirect(url_for('auth.admin_signup'))
        hashed_pw = generate_password_hash(password)
        get_collection('users').insert_one({'username': username, 'password': hashed_pw, 'role': 'admin'})
        flash('Admin signup successful! Please login.')
        return redirect(url_for('auth.login'))
    return render_template(
        'admin_signup.html',
        page_title='Admin Registration',
        auth_title='Admin Registration',
        auth_subtitle='Create your admin account.',
        body_class='admin-register-page'
    )

async function getJSON(url) {
    const r = await fetch(url);
    return r.json();
}

async function sendJSON(url, method, payload) {
    const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
    return r.json();
}

function toast(msg) {
    alert(msg);
}

async function loadOverview() {
    const data = await getJSON('/api/reports/overview');
    const el = document.getElementById('report-overview');
    el.innerHTML = `
        <div><strong>Month:</strong> ${data.month || '--'}</div>
        <div><strong>Headcount:</strong> ${data.headcount_total || 0}</div>
        <div><strong>On Leave:</strong> ${data.currently_on_leave || 0}</div>
        <div><strong>Payroll Net:</strong> Rs ${Number(data.payroll_total_net || 0).toLocaleString()}</div>
    `;
}

function renderReportRows(rows) {
    const tb = document.getElementById('report-table');
    tb.innerHTML = '';
    rows.forEach((r) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.metric}</td><td>${r.value}</td>`;
        tb.appendChild(tr);
    });
}

async function loadAttendanceReport() {
    const rows = await getJSON('/api/reports/attendance');
    const summary = [
        { metric: 'Employees Tracked', value: rows.length },
        { metric: 'Total Present Days', value: rows.reduce((a, b) => a + (b.present_days || 0), 0) },
        { metric: 'Total Late Marks', value: rows.reduce((a, b) => a + (b.late_marks || 0), 0) },
        { metric: 'Total Overtime Hours', value: rows.reduce((a, b) => a + Number(b.overtime_hours || 0), 0).toFixed(2) },
    ];
    renderReportRows(summary);
}

async function loadPayrollReport() {
    const data = await getJSON('/api/reports/payroll');
    const rows = data.rows || [];
    const summary = [
        { metric: 'Employees Paid', value: rows.length },
        { metric: 'Gross Total', value: `Rs ${rows.reduce((a, b) => a + Number(b.gross || 0), 0).toLocaleString()}` },
        { metric: 'Deductions Total', value: `Rs ${rows.reduce((a, b) => a + Number(b.deductions || 0), 0).toLocaleString()}` },
        { metric: 'Net Total', value: `Rs ${rows.reduce((a, b) => a + Number(b.net || 0), 0).toLocaleString()}` },
    ];
    renderReportRows(summary);
}

async function loadAttritionReport() {
    const data = await getJSON('/api/reports/attrition');
    renderReportRows([
        { metric: 'Total Employees', value: data.total_employees || 0 },
        { metric: 'Exited Employees', value: data.exited_employees || 0 },
        { metric: 'Attrition Rate', value: `${data.attrition_rate_percent || 0}%` },
    ]);
}

async function loadExpenses() {
    const rows = await getJSON('/api/expenses');
    const tb = document.getElementById('expense-table');
    tb.innerHTML = '';
    rows.forEach((e) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${e.emp_id || '--'}</td>
            <td>${e.category || '--'}</td>
            <td>Rs ${Number(e.amount || 0).toLocaleString()}</td>
            <td>${e.status || '--'}</td>
            <td>${e.status === 'Pending' ? `<button class="btn btn-success-gradient btn-sm approve-expense" data-id="${e.id}">Approve</button>` : '--'}</td>
        `;
        tb.appendChild(tr);
    });
    document.querySelectorAll('.approve-expense').forEach((btn) => {
        btn.addEventListener('click', async function () {
            const data = await sendJSON(`/api/expenses/${this.dataset.id}/approve`, 'POST', {});
            if (data.success) {
                toast('Expense approved');
                loadExpenses();
            } else {
                toast(data.error || 'Could not approve');
            }
        });
    });
}

async function loadAudit() {
    const rows = await getJSON('/api/audit-logs');
    const tb = document.getElementById('audit-table');
    tb.innerHTML = '';
    rows.slice(0, 30).forEach((r) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${(r.created_on || '').replace('T', ' ').slice(0, 16)}</td>
            <td>${r.action || '--'}</td>
            <td>${r.actor_role || '--'} ${r.actor_emp_id ? `(${r.actor_emp_id})` : ''}</td>
        `;
        tb.appendChild(tr);
    });
}

document.addEventListener('DOMContentLoaded', function () {
    loadOverview();
    loadExpenses();
    loadAudit();

    document.getElementById('load-attendance-report').addEventListener('click', loadAttendanceReport);
    document.getElementById('load-payroll-report').addEventListener('click', loadPayrollReport);
    document.getElementById('load-attrition-report').addEventListener('click', loadAttritionReport);
    document.getElementById('load-audit').addEventListener('click', loadAudit);

    document.getElementById('attendance-policy-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = {
            shift_start: this.shift_start.value || '09:30',
            shift_end: this.shift_end.value || '18:30',
            grace_minutes: Number(this.grace_minutes.value || 15),
        };
        const data = await sendJSON('/api/policy/attendance', 'PUT', payload);
        toast(data.success ? 'Attendance policy saved' : (data.error || 'Failed'));
    });

    document.getElementById('leave-policy-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = {
            annual: {
                CL: Number(this.cl.value || 12),
                SL: Number(this.sl.value || 12),
                PL: Number(this.pl.value || 18),
            },
        };
        const data = await sendJSON('/api/policy/leave', 'PUT', payload);
        toast(data.success ? 'Leave policy saved' : (data.error || 'Failed'));
    });

    document.getElementById('role-assign-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = { emp_id: this.emp_id.value, role: this.role.value };
        const data = await sendJSON('/api/admin/create-user', 'POST', payload);
        toast(data.success ? 'Role assigned' : (data.error || 'Failed'));
    });

    document.getElementById('onboarding-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const empId = this.emp_id.value;
        const payload = {
            documents_submitted: this.documents_submitted.checked,
            it_assets_allocated: this.it_assets_allocated.checked,
            orientation_completed: this.orientation_completed.checked,
        };
        const data = await sendJSON(`/api/onboarding/${empId}`, 'PUT', payload);
        toast(data.success ? 'Onboarding updated' : (data.error || 'Failed'));
    });

    document.getElementById('offboarding-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = {
            reason: this.reason.value,
            last_working_day: this.last_working_day.value,
        };
        const data = await sendJSON(`/api/offboarding/initiate/${this.emp_id.value}`, 'POST', payload);
        toast(data.success ? 'Offboarding initiated' : (data.error || 'Failed'));
    });
});

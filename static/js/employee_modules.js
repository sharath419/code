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

async function loadProfile() {
    const p = await getJSON('/api/profile');
    const form = document.getElementById('profile-form');
    form.phone.value = p.phone || '';
    form.address.value = p.address || '';
}

async function loadNotifications() {
    const rows = await getJSON('/api/notifications');
    const list = document.getElementById('notification-list');
    list.innerHTML = '';
    if (!rows.length) {
        list.innerHTML = '<p class="text-muted mb-0">No notifications.</p>';
        return;
    }
    rows.forEach((n) => {
        const item = document.createElement('div');
        item.className = 'soft-box mb-2';
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <strong>${n.title || '--'}</strong>
                <small>${(n.created_on || '').replace('T', ' ').slice(0, 16)}</small>
            </div>
            <div class="small mt-1">${n.message || ''}</div>
            ${n.is_read ? '' : `<button class="btn btn-glass btn-sm mt-2 mark-read" data-id="${n.id}">Mark as read</button>`}
        `;
        list.appendChild(item);
    });
    document.querySelectorAll('.mark-read').forEach((btn) => {
        btn.addEventListener('click', async function () {
            await sendJSON(`/api/notifications/${this.dataset.id}/read`, 'POST', {});
            loadNotifications();
        });
    });
}

async function loadAttendanceSummary() {
    const data = await getJSON('/api/attendance/summary');
    const el = document.getElementById('attendance-summary');
    el.innerHTML = `
        <div class="row">
            <div class="col-6 inline-metric">Present Days<strong>${data.present_days || 0}</strong></div>
            <div class="col-6 inline-metric">Half Days<strong>${data.half_days || 0}</strong></div>
            <div class="col-6 inline-metric mt-2">Late Marks<strong>${data.late_marks || 0}</strong></div>
            <div class="col-6 inline-metric mt-2">Overtime<strong>${Number(data.overtime_hours || 0).toFixed(2)} h</strong></div>
        </div>
    `;
}

async function loadLeaveBalance() {
    const b = await getJSON('/api/leave-balance');
    document.getElementById('bal-cl').textContent = b.CL ?? 0;
    document.getElementById('bal-sl').textContent = b.SL ?? 0;
    document.getElementById('bal-pl').textContent = b.PL ?? 0;
}

async function loadExpenseHistory() {
    const rows = await getJSON('/api/expenses');
    const tb = document.getElementById('expense-history');
    tb.innerHTML = '';
    rows.forEach((e) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${e.category || '--'}</td>
            <td>Rs ${Number(e.amount || 0).toLocaleString()}</td>
            <td>${e.status || '--'}</td>
            <td>${(e.submitted_on || '').slice(0, 10)}</td>
        `;
        tb.appendChild(tr);
    });
}

async function loadLeaveHistory() {
    const rows = await getJSON('/api/leave-history');
    const tb = document.getElementById('leave-history');
    tb.innerHTML = '';
    rows.forEach((l) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${l.leave_type || '--'}</td>
            <td>${l.from_date || '--'}</td>
            <td>${l.to_date || '--'}</td>
            <td>${l.status || '--'}</td>
        `;
        tb.appendChild(tr);
    });
}

document.addEventListener('DOMContentLoaded', function () {
    loadProfile();
    loadNotifications();
    loadAttendanceSummary();
    loadLeaveBalance();
    loadExpenseHistory();
    loadLeaveHistory();

    document.getElementById('refresh-notifications').addEventListener('click', loadNotifications);

    document.getElementById('profile-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = { phone: this.phone.value, address: this.address.value };
        const data = await sendJSON('/api/profile', 'PUT', payload);
        toast(data.success ? 'Profile updated' : (data.error || 'Failed'));
    });

    document.getElementById('expense-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = {
            category: this.category.value,
            amount: Number(this.amount.value || 0),
            description: this.description.value,
        };
        const data = await sendJSON('/api/expenses', 'POST', payload);
        if (data.success) {
            toast('Expense submitted');
            this.reset();
            loadExpenseHistory();
        } else {
            toast(data.error || 'Failed');
        }
    });
});

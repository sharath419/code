// Employee Dashboard JavaScript with AJAX

document.addEventListener('DOMContentLoaded', function() {
    // Punch In
    const punchInBtn = document.getElementById('punch-in');
    if (punchInBtn) {
        punchInBtn.addEventListener('click', function() {
            fetch('/api/punch-in', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Punched in at ' + new Date(data.punch_in).toLocaleTimeString());
                    this.disabled = true;
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Punch Out
    const punchOutBtn = document.getElementById('punch-out');
    if (punchOutBtn) {
        punchOutBtn.addEventListener('click', function() {
            fetch('/api/punch-out', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Punched out at ' + new Date(data.punch_out).toLocaleTimeString());
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Leave Application
    const leaveForm = document.getElementById('leave-form');
    if (leaveForm) {
        leaveForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const leaveData = {
                from_date: this.querySelector('input[name="from_date"]').value,
                to_date: this.querySelector('input[name="to_date"]').value,
                reason: this.querySelector('textarea[name="reason"]').value,
                half_day: this.querySelector('select[name="leave_type"]').value === 'half'
            };
            fetch('/api/apply-leave', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(leaveData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Leave applied successfully!');
                    this.reset();
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Download Salary Slip
    const downloadSlipBtn = document.getElementById('download-slip');
    if (downloadSlipBtn) {
        downloadSlipBtn.addEventListener('click', function() {
            window.location.href = '/api/download-slip';
        });
    }

    // Load Meetings
    loadMeetings();
});

function loadMeetings() {
    fetch('/api/get-meetings')
        .then(response => response.json())
        .then(data => {
            const meetingList = document.getElementById('meeting-list');
            if (meetingList) {
                meetingList.innerHTML = '';
                data.forEach(meeting => {
                    const li = document.createElement('li');
                    li.className = 'list-group-item d-flex justify-content-between align-items-start';
                    const left = document.createElement('div');
                    left.innerHTML = `<div><strong>${meeting.title}</strong><br><small>${meeting.message}</small><br><em>${new Date(meeting.created_on).toLocaleDateString()}</em></div>`;
                    const right = document.createElement('div');
                    // If not read, show mark-as-read button
                    if (!meeting.is_read) {
                        const markBtn = document.createElement('button');
                        markBtn.className = 'btn btn-sm btn-primary me-2';
                        markBtn.textContent = 'Mark as read';
                        markBtn.addEventListener('click', function() {
                            fetch(`/api/mark-meeting-read/${meeting._id}`, { method: 'POST' })
                                .then(resp => resp.json())
                                .then(res => {
                                    if (res.success) {
                                        loadMeetings();
                                    } else {
                                        alert('Error: ' + (res.error || 'Could not mark as read'));
                                    }
                                })
                                .catch(err => console.error('Error:', err));
                        });
                        right.appendChild(markBtn);
                    } else {
                        const readBadge = document.createElement('span');
                        readBadge.className = 'badge bg-success me-2';
                        readBadge.textContent = 'Read';
                        right.appendChild(readBadge);
                    }
                    li.appendChild(left);
                    li.appendChild(right);
                    meetingList.appendChild(li);
                });
            }
        })
        .catch(error => console.error('Error:', error));
}

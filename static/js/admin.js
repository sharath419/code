// Admin Dashboard JavaScript with AJAX

document.addEventListener('DOMContentLoaded', function() {
    // Add Employee Form
    const addEmployeeForm = document.getElementById('add-employee-form');
    if (addEmployeeForm) {
        addEmployeeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const employeeData = {
                name: this.querySelector('input[name="name"]').value,
                department: this.querySelector('input[name="department"]').value,
                designation: this.querySelector('input[name="designation"]').value,
                phone: this.querySelector('input[name="phone"]').value,
                address: this.querySelector('input[name="address"]').value,
                experience: parseInt(this.querySelector('input[name="experience"]').value),
                salary: parseFloat(this.querySelector('input[name="salary"]').value),
                password: this.querySelector('input[name="password"]').value
            };
            fetch('/api/add-employee', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(employeeData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Employee added successfully! ID: ' + data.emp_id);
                    this.reset();
                    location.reload(); // Reload to show new employee
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Post Meeting Form
    const meetingForm = document.getElementById('meeting-form');
    if (meetingForm) {
        meetingForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const meetingData = {
                title: this.querySelector('input[name="title"]').value,
                message: this.querySelector('textarea[name="message"]').value
            };
            fetch('/api/post-meeting', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(meetingData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Meeting posted successfully!');
                    meetingForm.reset();
                    loadAdminMeetings();
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Load Meetings
    loadAdminMeetings();

    // Approve Leave Buttons
    document.querySelectorAll('.approve-leave').forEach(btn => {
        btn.addEventListener('click', function() {
            const leaveId = this.getAttribute('data-leave-id');
            if (confirm('Approve this leave request?')) {
                fetch(`/api/approve-leave/${leaveId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Leave approved!');
                        location.reload();
                    } else {
                        alert('Error: ' + data.error);
                    }
                })
                .catch(error => console.error('Error:', error));
            }
        });
    });

    // Reject Leave Buttons
    document.querySelectorAll('.reject-leave').forEach(btn => {
        btn.addEventListener('click', function() {
            const leaveId = this.getAttribute('data-leave-id');
            if (confirm('Reject this leave request?')) {
                fetch(`/api/reject-leave/${leaveId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Leave rejected!');
                        location.reload();
                    } else {
                        alert('Error: ' + data.error);
                    }
                })
                .catch(error => console.error('Error:', error));
            }
        });
    });
});

function loadAdminMeetings() {
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
                    const readCount = meeting.read_by ? meeting.read_by.length : 0;
                    const readBadge = document.createElement('span');
                    readBadge.className = 'badge bg-secondary me-2';
                    readBadge.textContent = `Reads: ${readCount}`;
                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'btn btn-sm btn-danger';
                    removeBtn.textContent = 'Remove';
                    removeBtn.setAttribute('data-id', meeting._id);
                    removeBtn.addEventListener('click', function() {
                        if (!confirm('Remove this announcement for all employees?')) return;
                        fetch(`/api/delete-meeting/${meeting._id}`, { method: 'DELETE' })
                            .then(resp => resp.json())
                            .then(res => {
                                if (res.success) {
                                    loadAdminMeetings();
                                } else {
                                    alert('Error: ' + (res.error || 'Could not delete'));
                                }
                            })
                            .catch(err => console.error('Error:', err));
                    });
                    right.appendChild(readBadge);
                    right.appendChild(removeBtn);
                    li.appendChild(left);
                    li.appendChild(right);
                    meetingList.appendChild(li);
                });
            }
        })
        .catch(error => console.error('Error:', error));
}

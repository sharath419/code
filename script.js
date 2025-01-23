document.getElementById('bookingForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent form submission

    // Get form values
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;
    const checkin = document.getElementById('checkin').value;
    const checkout = document.getElementById('checkout').value;
    const roomType = document.getElementById('roomType').value;

    // Process booking (for demonstration purposes, we'll just log the values)
    console.log('Booking Details:');
    console.log('Name:', name);
    console.log('Email:', email);
    console.log('Check-in Date:', checkin);
    console.log('Check-out Date:', checkout);
    console.log('Room Type:', roomType);

    // Display confirmation message
    alert('Booking successful! Thank you, ' + name + '.');
});
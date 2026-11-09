document.getElementById('form-elegibilidad').addEventListener('submit', async function(event) {
    event.preventDefault();

    const nuevoEstado = document.getElementById('selector-estado').value;

    try {
        const response = await fetch('/api/elegibilidad', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nuevo_estado: nuevoEstado })
        });

        const data = await response.json();

        if (response.ok) {
            // Actualiza la pantalla para que el usuario vea el cambio
            document.getElementById('texto-estado').innerText = data.estado_actual;
            alert(data.mensaje);
        } else {
            alert("Error al intentar guardar el estado.");
        }
    } catch (error) {
        console.error('Error de conexión:', error);
    }
});
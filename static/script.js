const selectorEstado = document.getElementById('selector-estado');
const contenedorMotivo = document.getElementById('contenedor-motivo');
const inputMotivo = document.getElementById('input-motivo');
const textoEstado = document.getElementById('texto-estado');

const ETIQUETAS = {
    APTO: 'Apto',
    DIFERIDO_TEMPORAL: 'Diferido temporal',
    RECHAZADO_PERMANENTE: 'Rechazado permanente',
};

let estadoActual = textoEstado.dataset.valor;

// Escucha cuando el usuario cambia la opción del selector
selectorEstado.addEventListener('change', function() {
    if (this.value !== estadoActual) {
        contenedorMotivo.style.display = 'block';
        inputMotivo.required = true; // obligatorio en el navegador
    } else {
        contenedorMotivo.style.display = 'none';
        inputMotivo.required = false;
        inputMotivo.value = '';
    }
});
document.getElementById('form-elegibilidad').addEventListener('submit', async function(event) {
    event.preventDefault();

    const nuevoEstado = selectorEstado.value;
    const motivo = inputMotivo.value;

    if (nuevoEstado === estadoActual) {
        alert("No hubo cambio de estado. No se guardó nada.")
        return;
    }

    try {
        const response = await fetch('/api/elegibilidad', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nuevo_estado: nuevoEstado, motivo: motivo })
        });

        const data = await response.json();

        if (response.ok) {
            // Actualiza la pantalla para que el usuario vea el cambio
            estadoActual = data.estado;
            textoEstado.dataset.valor = data.estado;
            textoEstado.innerText = ETIQUETAS[data.estado] ?? data.estado;
            alert(data.mensaje);

            inputMotivo.value = '';
            contenedorMotivo.style.display = 'none';
            inputMotivo.required = false;
            
        } else {
            alert("Error: " + data.detail);
        }
    } catch (error) {
        console.error('Error de conexión:', error);
    }
});
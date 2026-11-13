const selectorEstado = document.getElementById('selector-estado');
const contenedorMotivo = document.getElementById('contenedor-motivo');
const inputMotivo = document.getElementById('input-motivo');
const textoEstado = document.getElementById('texto-estado');
const msgFeedback = document.getElementById('msg-feedback');

const ETIQUETAS = {
    APTO: 'Apto',
    DIFERIDO_TEMPORAL: 'Diferido temporal',
    RECHAZADO_PERMANENTE: 'Rechazado permanente',
};

function textoError(detail) {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(d => d.msg).join('. ');
    return 'Ocurrió un error inesperado.';
}

function mostrarMensaje(texto, tipo) {
    msgFeedback.textContent = texto;
    msgFeedback.className = 'msg ' + tipo;
    msgFeedback.style.display = 'block';
}

function iniciarFormulario() {
    let estadoActual = textoEstado.dataset.valor;

    // Pide motivo ante cualquier cambio de estado
    selectorEstado.addEventListener('change', function () {
        if (this.value !== estadoActual) {
            contenedorMotivo.style.display = 'block';
            inputMotivo.required = true;
        } else {
            contenedorMotivo.style.display = 'none';
            inputMotivo.required = false;
            inputMotivo.value = '';
        }
    });

    document.getElementById('form-elegibilidad').addEventListener('submit', async function (event) {
        event.preventDefault();

        const nuevoEstado = selectorEstado.value;
        const motivo = inputMotivo.value.trim();

        if (nuevoEstado === estadoActual) {
            mostrarMensaje('No hubo cambio de estado. No se guardó nada.', 'aviso');
            return;
        }

        if (!motivo) {
            mostrarMensaje('Debes ingresar el motivo para cambiar el estado del donante.', 'error');
            inputMotivo.focus();
            return;
        }

        try {
            const response = await fetch('/api/elegibilidad', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nuevo_estado: nuevoEstado, motivo: motivo })
            });

            const data = await response.json();

            if (response.ok) {
                estadoActual = data.estado;
                textoEstado.dataset.valor = data.estado;
                textoEstado.innerText = ETIQUETAS[data.estado] ?? data.estado;
                textoEstado.classList.remove('apto', 'no-apto', 'rechazado', 'sin-evaluar');

                if (data.estado === 'APTO') {
                    textoEstado.classList.add('apto');
                } else if (data.estado === 'DIFERIDO_TEMPORAL') {
                    textoEstado.classList.add('no-apto');
                } else if (data.estado === 'RECHAZADO_PERMANENTE') {
                    textoEstado.classList.add('rechazado');
                }

                mostrarMensaje(data.mensaje, 'exito');

                inputMotivo.value = '';
                contenedorMotivo.style.display = 'none';
                inputMotivo.required = false;
            } else {
                mostrarMensaje('Error: ' + textoError(data.detail), 'error');
            }
        } catch (error) {
            console.error('Error de conexión:', error);
            mostrarMensaje('No se pudo conectar con el servidor.', 'error');
        }
    });
}

// el formulario solo existe si el usuario tiene permiso para modificar
if (selectorEstado) {
    iniciarFormulario();
}
const inputBuscarRun = document.getElementById('input-buscar-run');
const btnBuscarRun = document.getElementById('btn-buscar-run');
const msgBuscar = document.getElementById('msg-buscar');
const donanteNombre = document.getElementById('donante-nombre');
const donanteRun = document.getElementById('donante-run');
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
    if (!msgFeedback) return;
    msgFeedback.textContent = texto;
    msgFeedback.className = 'msg ' + tipo;
    msgFeedback.style.display = 'block';
}

function mostrarMensajeBusqueda(texto, tipo) {
    if (!msgBuscar) return;
    msgBuscar.textContent = texto;
    msgBuscar.className = 'msg ' + tipo;
    msgBuscar.style.display = 'block';
}

function ocultarMensajeBusqueda() {
    if (msgBuscar) msgBuscar.style.display = 'none';
}

function actualizarClasesEstado(estado) {
    if (!textoEstado) return;
    textoEstado.classList.remove('apto', 'no-apto', 'rechazado', 'sin-evaluar');
    if (estado === 'APTO') {
        textoEstado.classList.add('apto');
    } else if (estado === 'DIFERIDO_TEMPORAL') {
        textoEstado.classList.add('no-apto');
    } else if (estado === 'RECHAZADO_PERMANENTE') {
        textoEstado.classList.add('rechazado');
    } else {
        textoEstado.classList.add('sin-evaluar');
    }
}

let estadoActual = textoEstado ? (textoEstado.dataset.valor || '') : '';

function actualizarVisibilidadMotivo() {
    if (!selectorEstado || !contenedorMotivo || !inputMotivo) return;
    const nuevoEstado = selectorEstado.value;

    if (nuevoEstado && nuevoEstado !== estadoActual) {
        contenedorMotivo.style.display = 'block';
        inputMotivo.required = true;
    } else {
        contenedorMotivo.style.display = 'none';
        inputMotivo.required = false;
        inputMotivo.value = '';
    }
}

function cargarDonanteEnPantalla(data) {
    if (donanteNombre) donanteNombre.innerText = data.nombre;
    if (donanteRun) donanteRun.innerText = data.run;
    if (inputBuscarRun) inputBuscarRun.value = data.run;

    estadoActual = data.estado || '';
    if (textoEstado) {
        textoEstado.dataset.valor = estadoActual;
        textoEstado.innerText = ETIQUETAS[estadoActual] ?? 'Sin evaluar';
        actualizarClasesEstado(estadoActual);
    }

    if (selectorEstado) {
        if (data.estado) {
            selectorEstado.value = data.estado;
        } else {
            const opcionVacia = selectorEstado.querySelector('option[value=""]');
            if (opcionVacia) {
                selectorEstado.value = '';
            } else {
                selectorEstado.selectedIndex = 0;
            }
        }
    }

    actualizarVisibilidadMotivo();
    if (msgFeedback) msgFeedback.style.display = 'none';
}

async function buscarDonantePorRun() {
    if (!inputBuscarRun) return;
    const run = inputBuscarRun.value.trim();
    if (!run) {
        mostrarMensajeBusqueda('Por favor ingresa un RUN para buscar.', 'error');
        inputBuscarRun.focus();
        return;
    }

    try {
        const response = await fetch(`/api/elegibilidad/donante/${encodeURIComponent(run)}`);
        const data = await response.json();

        if (response.ok) {
            ocultarMensajeBusqueda();
            cargarDonanteEnPantalla(data);
        } else {
            mostrarMensajeBusqueda('Error: ' + textoError(data.detail), 'error');
        }
    } catch (err) {
        console.error('Error de conexión:', err);
        mostrarMensajeBusqueda('No se pudo conectar con el servidor.', 'error');
    }
}

function iniciarFormulario() {
    // Configura búsqueda por RUN
    if (btnBuscarRun) {
        btnBuscarRun.addEventListener('click', buscarDonantePorRun);
    }
    if (inputBuscarRun) {
        inputBuscarRun.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                buscarDonantePorRun();
            }
        });
    }

    // Al cambiar la opción del selector
    if (selectorEstado) {
        selectorEstado.addEventListener('change', actualizarVisibilidadMotivo);
    }

    // Inicializa la visibilidad de motivo en base al donante cargado inicialmente
    actualizarVisibilidadMotivo();

    const form = document.getElementById('form-elegibilidad');
    if (!form) return;

    form.addEventListener('submit', async function (event) {
        event.preventDefault();

        const nuevoEstado = selectorEstado.value;
        const motivo = inputMotivo.value.trim();
        const runTexto = donanteRun ? donanteRun.innerText.trim() : '';
        const runSeleccionado = (runTexto && runTexto !== '—') ? runTexto : (inputBuscarRun ? inputBuscarRun.value.trim() : null);

        if (!runSeleccionado) {
            mostrarMensaje('Debes buscar un donante por su RUN antes de guardar el estado.', 'error');
            if (inputBuscarRun) inputBuscarRun.focus();
            return;
        }

        if (!nuevoEstado) {
            mostrarMensaje('Debes seleccionar un estado de elegibilidad.', 'error');
            selectorEstado.focus();
            return;
        }

        if (nuevoEstado === estadoActual) {
            mostrarMensaje('No hubo cambio de estado. No se guardó nada.', 'aviso');
            return;
        }

        if (!motivo) {
            contenedorMotivo.style.display = 'block';
            inputMotivo.required = true;
            mostrarMensaje('Debes ingresar el motivo para cambiar el estado del donante.', 'error');
            inputMotivo.focus();
            return;
        }

        try {
            const response = await fetch('/api/elegibilidad', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    run: runSeleccionado,
                    nuevo_estado: nuevoEstado,
                    motivo: motivo
                })
            });

            const data = await response.json();

            if (response.ok) {
                estadoActual = data.estado;
                if (textoEstado) {
                    textoEstado.dataset.valor = data.estado;
                    textoEstado.innerText = ETIQUETAS[data.estado] ?? data.estado;
                    actualizarClasesEstado(data.estado);
                }

                mostrarMensaje(data.mensaje, 'exito');

                inputMotivo.value = '';
                actualizarVisibilidadMotivo();
            } else {
                mostrarMensaje('Error: ' + textoError(data.detail), 'error');
            }
        } catch (error) {
            console.error('Error de conexión:', error);
            mostrarMensaje('No se pudo conectar con el servidor.', 'error');
        }
    });
}

iniciarFormulario();
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Envuelve las respuestas de error de DRF en un formato uniforme:

    {
        "status": "error",
        "message": "Mensaje claro",
        "errors": {...}   # opcional, con el detalle original de DRF
    }
    """
    # Primero dejamos que DRF haga lo suyo (ValidationError, NotFound, etc.)
    response = exception_handler(exc, context)

    # 🔴 Errores NO manejados por DRF -> algo serio (500)
    if response is None:
        # Logueamos el error SIEMPRE
        logger.exception("Unhandled exception", exc_info=exc)

        # En desarrollo podés querer ver más info
        if settings.DEBUG:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),          # mensaje crudo
                    "errors": repr(exc),          # algo más de contexto
                },
                status=500,
            )

        # En producción mantenemos el mensaje genérico
        return Response(
            {
                "status": "error",
                "message": "Error interno del servidor."
            },
            status=500,
        )

    # 🟡 Errores manejados por DRF (400, 401, 403, 404, 422, etc.)
    data = response.data
    message = "Error en la solicitud."

    if isinstance(data, dict):
        # Caso típico: {"detail": "..."}
        if "detail" in data:
            message = data["detail"]
        else:
            # Tomar el primer error de campo si viene en formato {campo: [errores]}
            first_key = next(iter(data.keys()), None)
            if first_key is not None:
                val = data[first_key]
                if isinstance(val, list) and val:
                    message = str(val[0])
                else:
                    message = str(val)
    else:
        # data es una lista u otro tipo → lo convertimos a string
        message = str(data)

    # En vez de tirar el contenido original, lo envolvemos
    response.data = {
        "status": "error",
        "message": message,
        "errors": data,   # 👈 detalle completo por si el front lo quiere usar
    }

    return response

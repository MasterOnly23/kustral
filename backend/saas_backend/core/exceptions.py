from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Envuelve las respuestas de error de DRF en un formato uniforme:
    {
      "status": "error",
      "message": "Mensaje claro"
    }
    """
    response = exception_handler(exc, context)

    # Errores no manejados por DRF -> 500 genérico
    if response is None:
        return Response(
            {
                "status": "error",
                "message": "Error interno del servidor."
            },
            status=500,
        )

    data = response.data
    message = "Error en la solicitud."

    if isinstance(data, dict):
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
        message = str(data)

    return Response(
        {
            "status": "error",
            "message": message,
        },
        status=response.status_code,
    )

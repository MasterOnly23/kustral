from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .serializers import UserSerializer


class MeView(APIView):
    """
    Devuelve la info del usuario logueado (para el frontend).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class GoogleLoginView(APIView):
    """
    Endpoint placeholder para login con Google.
    Más adelante vamos a:
      - Recibir un id_token del frontend.
      - Verificarlo con google-auth.
      - Crear/actualizar el usuario.
      - Devolver tokens JWT propios.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        return Response(
            {"detail": "Google login not implemented yet."},
            status=501,  # Not Implemented
        )

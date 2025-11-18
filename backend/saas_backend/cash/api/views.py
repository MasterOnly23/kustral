# cash/api/views.py

from django.utils.timezone import localdate

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from cash.models import DailyCash
from .serializers import DailyCashSerializer
from accounts.models import User


class DailyCashViewSet(viewsets.ModelViewSet):
    """
    CRUD de cierres de caja diarios.
    - Filtra por company según el usuario.
    - Encargado/Empleado sólo ven (y crean) para su sucursal.
    - Admin Empresa puede manejar cualquier sucursal de su empresa.
    """

    serializer_class = DailyCashSerializer
    queryset = DailyCash.objects.select_related("company", "branch", "closed_by")
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Superuser o Super Admin SaaS ven todo
        if user.is_superuser or getattr(user, "is_super_admin_saas", False):
            return qs

        # Sin empresa asignada -> nada
        if not user.company_id:
            return qs.none()

        qs = qs.filter(company=user.company)

        # Encargado / Empleado -> sólo su sucursal
        if user.branch_id and user.role in [
            User.Role.BRANCH_MANAGER,
            User.Role.EMPLOYEE,
        ]:
            qs = qs.filter(branch=user.branch)

        # Admin Empresa -> ve todas las sucursales de su empresa
        return qs

    def perform_create(self, serializer):
        user = self.request.user

        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        # Sin empresa asignada (salvo superadmin) -> error
        if not user.company_id and not is_global_admin:
            raise ValidationError("El usuario no tiene empresa asignada.")

        # Encargado / Empleado -> siempre su sucursal
        if user.role in [User.Role.BRANCH_MANAGER, User.Role.EMPLOYEE]:
            if not user.branch_id:
                raise ValidationError(
                    "El usuario no tiene sucursal asignada y no puede crear cierres."
                )

            serializer.save(
                company=user.company,
                branch=user.branch,
                closed_by=None,
            )
            return

        # Admin de empresa -> elige sucursal, pero dentro de su empresa
        if user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            branch = serializer.validated_data.get("branch")
            if branch is None:
                raise ValidationError("Debe seleccionar una sucursal para el cierre.")
            if branch.company_id != user.company_id:
                raise ValidationError(
                    "No puede cargar cierres para sucursales de otra empresa."
                )

            serializer.save(
                company=user.company,
                closed_by=None,
            )
            return

        # Super Admin SaaS / superuser -> puede crear para cualquier empresa/sucursal
        branch = serializer.validated_data.get("branch")
        company = serializer.validated_data.get("company")

        if branch and not company:
            company = branch.company

        if not company:
            raise ValidationError(
                "Debe indicar empresa y/o sucursal para crear el cierre."
            )

        serializer.save(company=company, closed_by=None)

    def perform_update(self, serializer):
        instance = serializer.save()
        # Si pasa a CONFIRMED y no tiene closed_by, lo setea automáticamente
        if (
            instance.status == DailyCash.Status.CONFIRMED
            and instance.closed_by is None
        ):
            instance.closed_by = self.request.user
            instance.save(update_fields=["closed_by"])

    @action(detail=False, methods=["get"])
    def today_status(self, request):
        """
        Estado del cierre de hoy para el usuario actual.

        Para encargados/empleados -> su sucursal.
        Para admin empresa -> (por ahora) su empresa + branch si tiene.
        Más adelante podemos hacer un endpoint especial para ver todas las
        sucursales a la vez.
        """
        user = request.user

        if not user.company_id:
            return Response(
                {"detail": "El usuario no tiene empresa asignada."},
                status=400,
            )

        today = localdate()
        qs = DailyCash.objects.filter(company=user.company, date=today)

        if user.branch_id:
            qs = qs.filter(branch=user.branch)

        daily = qs.first()

        if not daily:
            return Response(
                {
                    "date": today,
                    "has_closure": False,
                    "status": None,
                    "daily_cash_id": None,
                }
            )

        return Response(
            {
                "date": today,
                "has_closure": True,
                "status": daily.status,
                "daily_cash_id": daily.id,
            }
        )

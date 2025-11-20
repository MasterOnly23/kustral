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
    - Encargado/Empleado solo ven (y crean) para su sucursal.
    - Admin Empresa puede manejar cualquier sucursal de su empresa.
    - Superuser puede todo.
    """

    serializer_class = DailyCashSerializer
    queryset = DailyCash.objects.select_related("company", "branch", "closed_by")
    permission_classes = [permissions.IsAuthenticated]

    # ----------------------
    # LISTADO / FILTRADO
    # ----------------------
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return Response({
                "status": "success",
                "message": "Listado de cierres obtenido correctamente.",
                "data": {
                    "count": self.paginator.page.paginator.count,
                    "next": self.paginator.get_next_link(),
                    "previous": self.paginator.get_previous_link(),
                    "results": serializer.data
                }
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": "success",
            "message": "Listado de cierres obtenido correctamente.",
            "data": serializer.data
        })
    
    #----------------------
    # Retrieve
    #--------------------
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            {
                "status": "success",
                "message": "Cierre de caja obtenido correctamente.",
                "data": serializer.data,
            }
        )



    # ----------------------
    # RESPUESTAS UNIFORMES
    # ----------------------
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Cierre de caja creado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Cierre de caja actualizado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Cierre de caja actualizado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    # ----------------------
    # REGLAS DE NEGOCIO AL CREAR
    # ----------------------
    def perform_create(self, serializer):
        user = self.request.user
        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        if not user.company_id and not is_global_admin:
            raise ValidationError("El usuario no tiene empresa asignada.")

        today = localdate()
        date = serializer.validated_data.get("date")

        if date is None:
            raise ValidationError("La fecha del cierre es obligatoria.")

        # ❌ Bloquear fecha futura para todos
        if date > today:
            raise ValidationError("No se puede cargar un cierre para una fecha futura.")

        # ------------------------------
        # ENCARGADO / EMPLEADO -> solo HOY y su sucursal
        # ------------------------------
        if user.role in [User.Role.BRANCH_MANAGER, User.Role.EMPLOYEE]:
            if not user.branch_id:
                raise ValidationError(
                    "El usuario no tiene sucursal asignada y no puede crear cierres."
                )
            if date != today:
                raise ValidationError(
                    "Solo puede cargar el cierre de la fecha de hoy."
                )

            # Validar duplicado
            if DailyCash.objects.filter(
                company=user.company,
                branch=user.branch,
                date=date,
            ).exists():
                raise ValidationError(
                    "Ya existe un cierre de caja para hoy en esta sucursal."
                )

            serializer.save(
                company=user.company,
                branch=user.branch,
                closed_by=None,
            )
            return

        # ------------------------------
        # ADMIN EMPRESA -> cualquier fecha pasada/actual, sucursales de su empresa
        # ------------------------------
        if user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            branch = serializer.validated_data.get("branch")
            if branch is None:
                raise ValidationError("Debe seleccionar una sucursal para el cierre.")
            if branch.company_id != user.company_id:
                raise ValidationError(
                    "No puede cargar cierres para sucursales de otra empresa."
                )

            if DailyCash.objects.filter(
                company=user.company,
                branch=branch,
                date=date,
            ).exists():
                raise ValidationError(
                    "Ya existe un cierre de caja para esa fecha en esa sucursal."
                )

            serializer.save(
                company=user.company,
                closed_by=None,
            )
            return

        # ------------------------------
        # SUPER ADMIN / SUPERUSER
        # ------------------------------
        branch = serializer.validated_data.get("branch")
        company = serializer.validated_data.get("company")

        if branch and not company:
            company = branch.company

        if not company:
            raise ValidationError(
                "Debe indicar empresa y/o sucursal para crear el cierre."
            )

        if DailyCash.objects.filter(
            company=company,
            branch=branch,
            date=date,
        ).exists():
            raise ValidationError(
                "Ya existe un cierre de caja para esa fecha en esa sucursal."
            )

        serializer.save(company=company, closed_by=None)

    # ----------------------
    # UPDATE: setear closed_by al confirmar
    # ----------------------
    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        today = localdate()

        is_global_admin = user.is_superuser or getattr(user, "is_super_admin_saas", False)

        # ------------------------------
        # Encargado / Empleado
        # ------------------------------
        if user.role in [User.Role.BRANCH_MANAGER, User.Role.EMPLOYEE] and not is_global_admin:
            # Solo su sucursal
            if instance.branch_id != user.branch_id:
                raise ValidationError("No tiene permiso para editar cierres de otra sucursal.")

            # Solo hoy
            if instance.date != today:
                raise ValidationError("Solo puede editar el cierre del día de hoy.")

            # Solo si está en DRAFT
            if instance.status != DailyCash.Status.DRAFT:
                raise ValidationError("Solo puede editar cierres en estado borrador (DRAFT).")

        # ------------------------------
        # Admin Empresa
        # ------------------------------
        if user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            # Solo su empresa
            if instance.company_id != user.company_id:
                raise ValidationError("No tiene permiso para editar cierres de otra empresa.")

            # Solo si está en DRAFT
            if instance.status != DailyCash.Status.DRAFT:
                raise ValidationError("No puede editar cierres confirmados.")

        # ------------------------------
        # Superuser: sin restricciones
        # ------------------------------

        # Si se confirma (CONFIRMED), setear closed_by si no tenía
        updated = serializer.save()
        if updated.status == DailyCash.Status.CONFIRMED and updated.closed_by is None:
            updated.closed_by = user
            updated.save(update_fields=["closed_by"])


    # ----------------------
    # DESTROY
    # ----------------------
    def destroy(self, request, *args, **kwargs):
        user = request.user
        instance = self.get_object()

        is_global_admin = user.is_superuser or getattr(user, "is_super_admin_saas", False)

        # Encargado / Empleado: jamás pueden borrar
        if user.role in [User.Role.BRANCH_MANAGER, User.Role.EMPLOYEE] and not is_global_admin:
            return Response(
                {"status": "error", "message": "No tiene permiso para eliminar cierres."},
                status=403,
            )

        # Admin Empresa: puede borrar solo si es DRAFT y es de su empresa
        if user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            if instance.company_id != user.company_id:
                return Response(
                    {"status": "error", "message": "No tiene permiso para eliminar cierres de otra empresa."},
                    status=403,
                )

            if instance.status != DailyCash.Status.DRAFT:
                return Response(
                    {"status": "error", "message": "Solo puede eliminar cierres en estado borrador."},
                    status=400,
                )

        # Superuser: puede todo
        response = super().destroy(request, *args, **kwargs)
        return Response(
            {"status": "success", "message": "Cierre eliminado correctamente."},
            status=200,
        )


    # ----------------------
    # ESTADO DEL DÍA
    # ----------------------
    @action(detail=False, methods=["get"])
    def today_status(self, request):
        """
        Estado del cierre de hoy para el usuario actual.
        Respuesta:
        {
          "status": "success",
          "message": "...",
          "data": {
             "date": "YYYY-MM-DD",
             "has_closure": true/false,
             "status": "DRAFT"/"CONFIRMED"/null,
             "daily_cash_id": 123/null
          }
        }
        """
        user = request.user

        if not user.company_id:
            return Response(
                {
                    "status": "error",
                    "message": "El usuario no tiene empresa asignada.",
                },
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
                    "status": "success",
                    "message": "No hay cierre cargado para hoy.",
                    "data": {
                        "date": today,
                        "has_closure": False,
                        "status": None,
                        "daily_cash_id": None,
                    },
                }
            )

        return Response(
            {
                "status": "success",
                "message": "Estado de cierre del día obtenido correctamente.",
                "data": {
                    "date": today,
                    "has_closure": True,
                    "status": daily.status,
                    "daily_cash_id": daily.id,
                },
            }
        )

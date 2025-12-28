from django.utils.timezone import localdate

from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from attendance.models import AttendanceRecord
from .serializers import AttendanceRecordSerializer
from accounts.models import User


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    """
    CRUD de registros de presentismo.

    - Multi-empresa y multi-sucursal.
    - Reglas por rol:
      * Superuser: todo.
      * Admin Empresa: toda la empresa.
      * Encargado: solo su sucursal.
      * Empleado: solo puede ver sus propios registros.
    """

    serializer_class = AttendanceRecordSerializer
    queryset = AttendanceRecord.objects.select_related("company", "branch", "employee")
    permission_classes = [permissions.IsAuthenticated]

    # ---------- FILTRADO POR ROL ----------
    def get_queryset(self):
        qs = super().get_queryset().filter(is_deleted=False)
        user = self.request.user

        # Superuser o Super Admin SaaS ven todo
        if user.is_superuser or getattr(user, "is_super_admin_saas", False):
            return qs

        # Sin empresa -> nada
        if not user.company_id:
            return qs.none()

        qs = qs.filter(company=user.company)

        # Empleado: solo sus propios registros
        if user.role == User.Role.EMPLOYEE:
            return qs.filter(employee=user)

        # Encargado: solo su sucursal
        if user.branch_id and user.role == User.Role.BRANCH_MANAGER:
            qs = qs.filter(branch=user.branch)

        # Admin Empresa: toda la empresa
        return qs

    # ---------- RESPUESTAS UNIFORMES ----------
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return Response({
                "status": "success",
                "message": "Listado de presentismo obtenido correctamente.",
                "data": {
                    "count": self.paginator.page.paginator.count,
                    "next": self.paginator.get_next_link(),
                    "previous": self.paginator.get_previous_link(),
                    "results": serializer.data,
                },
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": "success",
            "message": "Listado de presentismo obtenido correctamente.",
            "data": serializer.data,
        })

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            {
                "status": "success",
                "message": "Registro de presentismo obtenido correctamente.",
                "data": serializer.data,
            }
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Registro de presentismo creado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Registro de presentismo actualizado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Registro de presentismo actualizado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    def destroy(self, request, *args, **kwargs):
        user = request.user
        instance = self.get_object()

        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        # Empleado: jamás puede borrar
        if user.role == User.Role.EMPLOYEE and not is_global_admin:
            return Response(
                {
                    "status": "error",
                    "message": "No tiene permiso para eliminar registros de asistencia.",
                },
                status=403,
            )

        # Encargado: solo registros de su sucursal
        if user.role == User.Role.BRANCH_MANAGER and not is_global_admin:
            if instance.branch_id != user.branch_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No tiene permiso para eliminar registros de otra sucursal.",
                    },
                    status=403,
                )

        # Admin Empresa: solo su empresa
        if user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            if instance.company_id != user.company_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No tiene permiso para eliminar registros de otra empresa.",
                    },
                    status=403,
                )

        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        instance.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])
        return Response(
            {
                "status": "success",
                "message": "Registro de presentismo eliminado correctamente.",
            },
            status=200,
        )

    # ---------- REGLAS AL CREAR / EDITAR ----------
    def perform_create(self, serializer):
        user = self.request.user
        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        if not user.company_id and not is_global_admin:
            raise ValidationError("El usuario no tiene empresa asignada.")

        employee = serializer.validated_data.get("employee")
        date = serializer.validated_data.get("date")

        if employee is None:
            raise ValidationError("Debe seleccionar un empleado.")

        # No permitir fechas futuras
        today = localdate()
        if date and date > today:
            raise ValidationError("No se puede cargar presentismo para una fecha futura.")

        # Empleado no puede crear
        if user.role == User.Role.EMPLOYEE and not is_global_admin:
            raise ValidationError("No tiene permiso para crear registros de asistencia.")

        # Encargado: solo empleados de su sucursal
        if user.role == User.Role.BRANCH_MANAGER and not is_global_admin:
            if employee.company_id != user.company_id or employee.branch_id != user.branch_id:
                raise ValidationError(
                    "Solo puede cargar presentismo para empleados de su sucursal."
                )
            serializer.save(
                company=user.company,
                branch=user.branch,
            )
            return

        # Admin Empresa: empleados de su empresa
        if user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            if employee.company_id != user.company_id:
                raise ValidationError(
                    "Solo puede cargar presentismo para empleados de su empresa."
                )
            # branch: usamos la del empleado
            serializer.save(
                company=user.company,
                branch=employee.branch,
            )
            return

        # Superuser / Super Admin: puede todo
        company = serializer.validated_data.get("company") or employee.company
        branch = serializer.validated_data.get("branch") or employee.branch

        if not company:
            raise ValidationError("No se pudo determinar la empresa para el registro.")

        serializer.save(company=company, branch=branch)

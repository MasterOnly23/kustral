from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from orders.models import InternalOrder
from .serializers import InternalOrderSerializer
from accounts.models import User
from rest_framework.exceptions import ValidationError


class InternalOrderViewSet(viewsets.ModelViewSet):
    queryset = InternalOrder.objects.select_related(
        "company", "branch", "created_by"
    ).prefetch_related("items")
    serializer_class = InternalOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    # -------------------------------------------------
    # FILTRADO SEGÚN ROL + SOFT DELETE
    # -------------------------------------------------
    def get_queryset(self):
        qs = super().get_queryset().filter(is_deleted=False)
        user = self.request.user

        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        # Superuser / Super Admin SaaS ven todo
        if is_global_admin:
            return qs

        # Si no tiene empresa → nada
        if not user.company_id:
            return qs.none()

        # Admin Empresa → ve toda la empresa
        if user.role == User.Role.ADMIN_COMPANY:
            return qs.filter(company=user.company)

        # Encargado → ve solo pedidos de su sucursal
        if user.role == User.Role.BRANCH_MANAGER:
            return qs.filter(company=user.company, branch=user.branch)

        # Empleado → no participa
        return qs.none()

    # -------------------------------------------------
    # RESPUESTAS UNIFORMES
    # -------------------------------------------------
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        ser = self.get_serializer(page or qs, many=True)

        if page is not None:
            return Response({
                "status": "success",
                "message": "Listado obtenido correctamente.",
                "data": {
                    "count": qs.count(),
                    "next": self.paginator.get_next_link(),
                    "previous": self.paginator.get_previous_link(),
                    "results": ser.data
                }
            })

        return Response({
            "status": "success",
            "message": "Listado obtenido correctamente.",
            "data": ser.data
        })

    def retrieve(self, request, *args, **kwargs):
        order = self.get_object()

        # Por si algún día cambian get_queryset
        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        ser = self.get_serializer(order)
        return Response({
            "status": "success",
            "message": "Pedido obtenido correctamente.",
            "data": ser.data
        })

    # -------------------------------------------------
    # CREACIÓN
    # -------------------------------------------------
    def create(self, request, *args, **kwargs):
        user = request.user

        # Solo Encargado, Admin Empresa o Superuser pueden crear
        if user.role not in [User.Role.BRANCH_MANAGER, User.Role.ADMIN_COMPANY] and \
                not (user.is_superuser or getattr(user, "is_super_admin_saas", False)):
            return Response(
                {
                    "status": "error",
                    "message": "No tiene permiso para crear pedidos.",
                },
                status=403,
            )

        data = request.data.copy()

        # ---- Encargado de sucursal ----
        if user.role == User.Role.BRANCH_MANAGER and not user.is_superuser:
            if not user.company_id or not user.branch_id:
                raise ValidationError(
                    "El usuario debe tener empresa y sucursal asignadas."
                )
            data["company"] = user.company_id
            data["branch"] = user.branch_id
            data["created_by"] = user.id

        # ---- Admin Empresa ----
        elif user.role == User.Role.ADMIN_COMPANY and not user.is_superuser:
            if not user.company_id:
                raise ValidationError("El usuario debe tener empresa asignada.")
            branch_id = data.get("branch")
            if not branch_id:
                raise ValidationError(
                    "Debe indicar la sucursal (branch) para el pedido."
                )
            data["company"] = user.company_id
            data["created_by"] = user.id

        # ---- Superuser / Super Admin SaaS ----
        else:
            if not data.get("company"):
                raise ValidationError(
                    "Debe indicar la empresa (company) para el pedido."
                )
            if not data.get("branch"):
                raise ValidationError(
                    "Debe indicar la sucursal (branch) para el pedido."
                )
            data["created_by"] = user.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        return Response(
            {
                "status": "success",
                "message": "Pedido creado correctamente.",
                "data": self.get_serializer(order).data,
            },
            status=201,
        )

    # -------------------------------------------------
    # REGLAS PARA EDITAR (SOLO PENDING, salvo superuser)
    # -------------------------------------------------
    def update(self, request, *args, **kwargs):
        order = self.get_object()
        user = request.user
        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        if not is_global_admin:
            # Empleado jamás edita
            if user.role == User.Role.EMPLOYEE:
                return Response(
                    {
                        "status": "error",
                        "message": "No tiene permiso para editar pedidos internos.",
                    },
                    status=403,
                )

            # Encargado: solo su sucursal
            if user.role == User.Role.BRANCH_MANAGER and order.branch_id != user.branch_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No puede editar pedidos de otra sucursal.",
                    },
                    status=403,
                )

            # Admin Empresa: solo su empresa
            if user.role == User.Role.ADMIN_COMPANY and order.company_id != user.company_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No puede editar pedidos de otra empresa.",
                    },
                    status=403,
                )

            # Solo si está en PENDING
            if order.status != InternalOrder.Status.PENDING:
                return Response(
                    {
                        "status": "error",
                        "message": "Solo se puede editar pedidos en estado PENDING.",
                    },
                    status=400,
                )

        response = super().update(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Pedido interno actualizado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    def partial_update(self, request, *args, **kwargs):
        order = self.get_object()
        user = request.user
        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        if not is_global_admin:
            if user.role == User.Role.EMPLOYEE:
                return Response(
                    {
                        "status": "error",
                        "message": "No tiene permiso para editar pedidos internos.",
                    },
                    status=403,
                )

            if user.role == User.Role.BRANCH_MANAGER and order.branch_id != user.branch_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No puede editar pedidos de otra sucursal.",
                    },
                    status=403,
                )

            if user.role == User.Role.ADMIN_COMPANY and order.company_id != user.company_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No puede editar pedidos de otra empresa.",
                    },
                    status=403,
                )

            if order.status != InternalOrder.Status.PENDING:
                return Response(
                    {
                        "status": "error",
                        "message": "Solo se puede editar pedidos en estado PENDING.",
                    },
                    status=400,
                )

        response = super().partial_update(request, *args, **kwargs)
        return Response(
            {
                "status": "success",
                "message": "Pedido interno actualizado correctamente.",
                "data": response.data,
            },
            status=response.status_code,
        )

    # -------------------------------------------------
    # SOFT DELETE (solo PENDING, salvo superuser)
    # -------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        user = request.user
        order = self.get_object()

        is_global_admin = user.is_superuser or getattr(
            user, "is_super_admin_saas", False
        )

        # Ya eliminado
        if getattr(order, "is_deleted", False):
            return Response(
                {
                    "status": "error",
                    "message": "El pedido interno ya fue eliminado.",
                },
                status=400,
            )

        # Empleado jamás borra
        if user.role == User.Role.EMPLOYEE and not is_global_admin:
            return Response(
                {
                    "status": "error",
                    "message": "No tiene permiso para eliminar pedidos internos.",
                },
                status=403,
            )

        # Encargado: solo su sucursal
        if user.role == User.Role.BRANCH_MANAGER and not is_global_admin:
            if order.branch_id != user.branch_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No puede eliminar pedidos de otra sucursal.",
                    },
                    status=403,
                )

        # Admin Empresa: solo su empresa
        if user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            if order.company_id != user.company_id:
                return Response(
                    {
                        "status": "error",
                        "message": "No puede eliminar pedidos de otra empresa.",
                    },
                    status=403,
                )

            # Admin Empresa: solo PENDING
            if order.status != InternalOrder.Status.PENDING:
                return Response(
                    {
                        "status": "error",
                        "message": "Solo se puede eliminar pedidos en estado PENDING.",
                    },
                    status=400,
                )

        # Superuser / Super Admin → sin restricción de estado

        # Soft delete
        order.is_deleted = True
        order.deleted_by = user
        order.deleted_at = timezone.now()
        order.save(update_fields=["is_deleted", "deleted_by", "deleted_at"])

        return Response(
            {
                "status": "success",
                "message": "Pedido interno eliminado correctamente.",
            },
            status=200,
        )

    # -------------------------------------------------
    # ACCIONES DE ESTADO
    # -------------------------------------------------
    def _change_status(self, order, new_status, user, date_field, user_field):
        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        setattr(order, date_field, timezone.now())
        setattr(order, user_field, user)
        order.status = new_status
        order.save()

        return Response({
            "status": "success",
            "message": f"Pedido actualizado a {new_status}.",
            "data": self.get_serializer(order).data
        })

    @action(detail=True, methods=["post"])
    def set_in_process(self, request, pk=None):
        order = self.get_object()
        user = request.user

        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        if user.role != User.Role.ADMIN_COMPANY and not user.is_superuser:
            return Response({"status": "error", "message": "No autorizado."}, 403)

        if order.status != InternalOrder.Status.PENDING:
            return Response(
                {"status": "error", "message": "Sólo se puede pasar desde PENDING."},
                400,
            )

        return self._change_status(
            order,
            InternalOrder.Status.IN_PROCESS,
            user,
            "in_process_date",
            "in_process_by",
        )

    @action(detail=True, methods=["post"])
    def set_sent(self, request, pk=None):
        order = self.get_object()
        user = request.user

        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        if user.role != User.Role.ADMIN_COMPANY and not user.is_superuser:
            return Response({"status": "error", "message": "No autorizado."}, 403)

        if order.status != InternalOrder.Status.IN_PROCESS:
            return Response(
                {"status": "error", "message": "Debe estar en IN_PROCESS."}, 400
            )

        return self._change_status(
            order,
            InternalOrder.Status.SENT,
            user,
            "sent_date",
            "sent_by",
        )

    @action(detail=True, methods=["post"])
    def set_delivered(self, request, pk=None):
        order = self.get_object()
        user = request.user

        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        if user.role != User.Role.BRANCH_MANAGER and not user.is_superuser:
            return Response({"status": "error", "message": "No autorizado."}, 403)

        if order.branch_id != user.branch_id:
            return Response(
                {"status": "error", "message": "Sólo su sucursal puede confirmar."},
                403,
            )

        if order.status != InternalOrder.Status.SENT:
            return Response(
                {"status": "error", "message": "Debe estar en SENT."}, 400
            )

        return self._change_status(
            order,
            InternalOrder.Status.DELIVERED,
            user,
            "delivered_date",
            "delivered_by",
        )

    @action(detail=True, methods=["post"])
    def set_cancelled(self, request, pk=None):
        order = self.get_object()
        user = request.user

        if getattr(order, "is_deleted", False):
            return Response(
                {"status": "error", "message": "El pedido interno no existe."},
                status=404,
            )

        # Admin Empresa siempre puede cancelar
        if user.role == User.Role.ADMIN_COMPANY or user.is_superuser:
            return self._change_status(
                order,
                InternalOrder.Status.CANCELLED,
                user,
                "cancelled_date",
                "cancelled_by",
            )

        # Encargado solo puede cancelar si el pedido está en PENDING y es de su sucursal
        if user.role == User.Role.BRANCH_MANAGER:
            if order.branch_id != user.branch_id:
                return Response(
                    {"status": "error", "message": "No autorizado."},
                    403,
                )
            if order.status != InternalOrder.Status.PENDING:
                return Response(
                    {
                        "status": "error",
                        "message": "Sólo puede cancelar pedidos en estado PENDING.",
                    },
                    400,
                )
            return self._change_status(
                order,
                InternalOrder.Status.CANCELLED,
                user,
                "cancelled_date",
                "cancelled_by",
            )

        return Response({"status": "error", "message": "No autorizado."}, 403)

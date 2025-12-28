from django.db.models import Sum, Count, Q
from django.utils.timezone import localdate
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from companies.models import Branch 
from cash.models import DailyCash
from attendance.models import AttendanceRecord as Attendance
from orders.models import InternalOrder  


class DashboardTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get_scope(self, user):
        """
        Define el alcance (multi-tenant) según rol.
        - Superuser / SuperAdminSaaS: puede ver todo (pero para MVP lo normal es filtrar por company si viene)
        - Admin Empresa: toda la empresa
        - Encargado: solo su sucursal
        """
        is_global_admin = user.is_superuser or getattr(user, "is_super_admin_saas", False)

        if is_global_admin:
            # opcional: permitir ?company=ID
            return {"company_id": None, "branch_id": None, "is_global_admin": True}

        if not user.company_id:
            return {"company_id": None, "branch_id": None, "is_global_admin": False}

        # Encargado/Empleado -> su sucursal
        if user.role in [User.Role.BRANCH_MANAGER, User.Role.EMPLOYEE] and user.branch_id:
            return {"company_id": user.company_id, "branch_id": user.branch_id, "is_global_admin": False}

        # Admin Empresa -> toda la empresa
        return {"company_id": user.company_id, "branch_id": None, "is_global_admin": False}

    def get(self, request):
        user = request.user
        today = localdate()

        scope = self.get_scope(user)

        # Si no tiene empresa asignada (y no es global admin), devolvemos mensaje claro
        if not scope["is_global_admin"] and not scope["company_id"]:
            return Response(
                {
                    "status": "error",
                    "message": "El usuario no tiene empresa asignada.",
                    "data": None,
                },
                status=400,
            )

        # ----------------------------
        # Branches base (las que aparecen en dashboard)
        # ----------------------------
        branches_qs = Branch.objects.all()

        # Global admin: opcionalmente puede filtrar por query param company
        if scope["is_global_admin"]:
            company_param = request.query_params.get("company")
            if company_param:
                branches_qs = branches_qs.filter(company_id=company_param)
        else:
            branches_qs = branches_qs.filter(company_id=scope["company_id"])

        if scope["branch_id"]:
            branches_qs = branches_qs.filter(id=scope["branch_id"])

        branches = list(branches_qs.values("id", "name", "company_id"))

        # Si no hay sucursales, devolvemos vacío
        if not branches:
            return Response(
                {
                    "status": "success",
                    "message": "Resumen del día obtenido correctamente.",
                    "data": {
                        "date": str(today),
                        "scope": {"company_id": scope["company_id"], "branch_id": scope["branch_id"]},
                        "kpis": {
                            "total_sales": "0.00",
                            "branches_total": 0,
                            "branches_cash_loaded": 0,
                            "attendance_loaded_branches": 0,
                            "orders_pending": 0,
                            "orders_in_process": 0,
                            "orders_sent": 0,
                            "orders_delivered": 0,
                            "absences": 0,
                            "late": 0,
                        },
                        "branches": [],
                    },
                },
                status=200,
            )

        branch_ids = [b["id"] for b in branches]

        # ----------------------------
        # DAILY CASH (hoy)
        # ----------------------------
        cash_qs = DailyCash.objects.filter(
            is_deleted=False,
            date=today,
            branch_id__in=branch_ids,
        )
        # Filtrado por company si hace falta (por si Branch no asegura relación)
        if not scope["is_global_admin"] and scope["company_id"]:
            cash_qs = cash_qs.filter(company_id=scope["company_id"])

        cash_by_branch = {
            row["branch_id"]: row
            for row in cash_qs.values("id", "branch_id", "status")
        }

        total_sales = cash_qs.aggregate(total=Sum("total_sales"))["total"] or 0

        # ----------------------------
        # ATTENDANCE (hoy) - (cargado si hay al menos 1 registro por sucursal)
        # ----------------------------
        attendance_qs = Attendance.objects.filter(
            is_deleted=False,
            date=today,
            branch_id__in=branch_ids,
        )
        if not scope["is_global_admin"] and scope["company_id"]:
            attendance_qs = attendance_qs.filter(company_id=scope["company_id"])

        attendance_loaded_branch_ids = set(
            attendance_qs.values_list("branch_id", flat=True).distinct()
        )

        ABSENT_CODES = ["A"]
        LATE_CODES = ["PT"]

        absences_count = attendance_qs.filter(status__in=ABSENT_CODES).count()
        late_count = attendance_qs.filter(status__in=LATE_CODES).count()
        attendance_breakdown = dict(
            attendance_qs.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )



        # ----------------------------
        # ORDERS (backlog acumulado)
        # ----------------------------
        orders_qs = InternalOrder.objects.filter(
            is_deleted=False,
            branch_id__in=branch_ids,
        )
        if not scope["is_global_admin"] and scope["company_id"]:
            orders_qs = orders_qs.filter(company_id=scope["company_id"])

        # Conteos por estado (en backlog)
        orders_counts = orders_qs.aggregate(
            pending=Count("id", filter=Q(status=InternalOrder.Status.PENDING)),
            in_process=Count("id", filter=Q(status=InternalOrder.Status.IN_PROCESS)),
            sent=Count("id", filter=Q(status=InternalOrder.Status.SENT)),
            delivered=Count("id", filter=Q(status=InternalOrder.Status.DELIVERED)),
        )

        # Conteos por sucursal
        orders_by_branch_raw = orders_qs.values("branch_id").annotate(
            pending=Count("id", filter=Q(status=InternalOrder.Status.PENDING)),
            in_process=Count("id", filter=Q(status=InternalOrder.Status.IN_PROCESS)),
            sent=Count("id", filter=Q(status=InternalOrder.Status.SENT)),
            delivered=Count("id", filter=Q(status=InternalOrder.Status.DELIVERED)),
        )
        orders_by_branch = {row["branch_id"]: row for row in orders_by_branch_raw}

        # ----------------------------
        # Armar respuesta por sucursal
        # ----------------------------
        branches_payload = []
        branches_cash_loaded = 0

        for b in branches:
            branch_id = b["id"]

            cash_info = cash_by_branch.get(branch_id)
            cash_loaded = cash_info is not None
            if cash_loaded:
                branches_cash_loaded += 1

            attendance_loaded = branch_id in attendance_loaded_branch_ids

            orders_info = orders_by_branch.get(branch_id, {})
            branches_payload.append(
                {
                    "branch_id": branch_id,
                    "branch_name": b["name"],
                    "cash": {
                        "loaded": cash_loaded,
                        "status": cash_info["status"] if cash_loaded else None,
                        "cash_id": cash_info["id"] if cash_loaded else None,
                    },
                    "attendance": {
                        "loaded": attendance_loaded,
                    },
                    "orders": {
                        "pending": orders_info.get("pending", 0),
                        "in_process": orders_info.get("in_process", 0),
                        "sent": orders_info.get("sent", 0),
                        "delivered": orders_info.get("delivered", 0),
                    },
                }
            )

        data = {
            "date": str(today),
            "scope": {
                "company_id": scope["company_id"],
                "branch_id": scope["branch_id"],
            },
            "kpis": {
                "total_sales": str(total_sales),
                "branches_total": len(branches),
                "branches_cash_loaded": branches_cash_loaded,
                "attendance_loaded_branches": len(attendance_loaded_branch_ids),
                "attendance_breakdown": attendance_breakdown,
                "orders_pending": orders_counts["pending"] or 0,
                "orders_in_process": orders_counts["in_process"] or 0,
                "orders_sent": orders_counts["sent"] or 0,
                "orders_delivered": orders_counts["delivered"] or 0,
                "absences": absences_count,
                "late": late_count,
            },
            "branches": branches_payload,
        }

        return Response(
            {
                "status": "success",
                "message": "Resumen del día obtenido correctamente.",
                "data": data,
            },
            status=200,
        )

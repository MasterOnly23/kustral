from django.utils.timezone import localdate

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.shortcuts import get_object_or_404

from cash.models import DailyCash, DailyCashPhoto
from .serializers import DailyCashSerializer, DailyCashPhotoSerializer
from accounts.models import User

#Compresion de imagen
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from cash.utils import move_photo_to_deleted_folder



def compress_image(uploaded_file, quality=70, max_dim=2500):
    """
    Comprime la imagen a JPG con calidad dada y limita el tamaño máximo del lado mayor.
    Devuelve un InMemoryUploadedFile listo para guardar.
    """
    image = Image.open(uploaded_file)

    # Aseguramos RGB (por si viene RGBA o paleta)
    if image.mode != "RGB":
        image = image.convert("RGB")

    width, height = image.size
    max_side = max(width, height)
    if max_side > max_dim:
        scale = max_dim / max_side
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size, Image.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)

    new_name_base = uploaded_file.name.rsplit(".", 1)[0]
    new_name = f"{new_name_base}.jpg"
    file_size = buffer.getbuffer().nbytes

    return InMemoryUploadedFile(
        buffer,
        field_name=getattr(uploaded_file, "field_name", "image"),
        name=new_name,
        content_type="image/jpeg",
        size=file_size,
        charset=None,
    )

class DailyCashViewSet(viewsets.ModelViewSet):
    """
    CRUD de cierres de caja diarios.

    - Filtra por company según el usuario.
    - Encargado/Empleado solo ven (y crean) para su sucursal.
    - Admin Empresa puede manejar cualquier sucursal de su empresa.
    - Superuser puede todo.
    """

    MAX_PHOTOS_PER_CASH = 5

    serializer_class = DailyCashSerializer
    queryset = DailyCash.objects.select_related(
        "company", "branch", "closed_by"
    ).prefetch_related("photos")
    permission_classes = [permissions.IsAuthenticated]

    # ----------------------
    # LISTADO / FILTRADO
    # ----------------------
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().filter(is_deleted=False))

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
        if instance.is_deleted:
            return Response(
                {
                    "status": "error",
                    "message": "El cierre de caja no existe.",
                },
                status=404,
            )
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
        # Traemos la instancia
        instance = self.get_object()

        # ⛔ Si está soft-deleted, se responde 404 y no se intenta actualizar
        if getattr(instance, "is_deleted", False):
            return Response(
                {
                    "status": "error",
                    "message": "El cierre de caja no existe.",
                },
                status=404,
            )

        # Delegamos en DRF para la lógica normal de update (serializer, validación, etc.)
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
        instance = self.get_object()

        if getattr(instance, "is_deleted", False):
            return Response(
                {
                    "status": "error",
                    "message": "El cierre de caja no existe.",
                },
                status=404,
            )

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

        if getattr(instance, "is_deleted", False):
            raise ValidationError("El cierre de caja no existe.")

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
    # ELIMINACIÓN LÓGICA
    # ----------------------

    @action(detail=True, methods=["delete"], url_path="soft_delete")
    def soft_delete(self, request, pk=None):
        daily_cash = self.get_object()
        user = request.user

        is_global_admin = user.is_superuser or getattr(user, "is_super_admin_saas", False)

        # Permisos (como ya lo hicimos antes)
        if not is_global_admin:
            if user.role == User.Role.ADMIN_COMPANY:
                if user.company_id != daily_cash.company_id:
                    return Response({"status": "error", "message": "No puede borrar cierres de otra empresa."}, status=403)
                if daily_cash.status != DailyCash.Status.DRAFT:
                    return Response({"status": "error", "message": "Solo puede borrar cierres en estado DRAFT."}, status=403)
            else:
                return Response({"status": "error", "message": "No tiene permiso."}, status=403)

        # Mover fotos a carpeta de eliminados
        for photo in daily_cash.photos.all():
            move_photo_to_deleted_folder(photo)

        # Soft delete
        daily_cash.is_deleted = True
        daily_cash.save(update_fields=["is_deleted"])

        return Response(
            {"status": "success", "message": "Cierre eliminado y fotos archivadas."},
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
    
    @action(detail=True, methods=["post"])
    def upload_photo(self, request, pk=None):
        daily_cash = self.get_object()
        user = request.user

        # Permisos
        if not self._can_manage_photos(user, daily_cash):
            return Response(
                {
                    "status": "error",
                    "message": "No tiene permiso para adjuntar fotos a este cierre.",
                },
                status=403,
            )

        files = request.FILES.getlist("photos")
        if not files:
            return Response(
                {
                    "status": "error",
                    "message": "Debe enviar al menos una foto en el campo 'photos'.",
                },
                status=400,
            )

        # Límite de fotos por cierre
        existing = daily_cash.photos.count()
        if existing + len(files) > self.MAX_PHOTOS_PER_CASH:
            remaining = max(self.MAX_PHOTOS_PER_CASH - existing, 0)
            return Response(
                {
                    "status": "error",
                    "message": f"Solo se permiten {self.MAX_PHOTOS_PER_CASH} fotos por cierre. "
                               f"Ya hay {existing} cargadas. Puede subir {remaining} más.",
                },
                status=400,
            )

        photo_serializer = DailyCashPhotoSerializer()

        created_count = 0
        for file in files:
            # Validar que sea imagen válida y <= 5MB
            photo_serializer.validate_image(file)

            # Comprimir (fuerte, calidad 70)
            compressed = compress_image(file, quality=70, max_dim=2500)

            from cash.models import DailyCashPhoto  # por si no estaba importado arriba
            DailyCashPhoto.objects.create(daily_cash=daily_cash, image=compressed)
            created_count += 1

        return Response(
            {
                "status": "success",
                "message": f"Se subieron {created_count} foto(s) correctamente.",
            }
        )
    
    @action(
        detail=True,
        methods=["delete"],
        url_path="photos/(?P<photo_id>[^/.]+)",
    )
    def delete_photo(self, request, pk=None, photo_id=None):
        """
        Elimina una foto específica de un cierre de caja.
        URL: DELETE /api/cash/daily/<dailycash_id>/photos/<photo_id>/
        """
        daily_cash = self.get_object()
        user = request.user

        # Permisos (mismas reglas que para subir)
        if not self._can_manage_photos(user, daily_cash):
            return Response(
                {
                    "status": "error",
                    "message": "No tiene permiso para eliminar fotos de este cierre.",
                },
                status=403,
            )

        from cash.models import DailyCashPhoto
        photo = get_object_or_404(DailyCashPhoto, id=photo_id, daily_cash=daily_cash)

        # Regla adicional: Encargado/Empleado no pueden eliminar fotos de cierres CONFIRMED
        if daily_cash.status == DailyCash.Status.CONFIRMED and \
            user.role in [User.Role.BRANCH_MANAGER, User.Role.EMPLOYEE] and not user.is_superuser:
            return Response(
                {"status": "error", "message": "No puede eliminar fotos de un cierre confirmado."},
                status=400,
            )

        photo.delete()

        return Response(
            {
                "status": "success",
                "message": "Foto eliminada correctamente.",
            }
        )
    
    def _can_manage_photos(self, user, daily_cash):
        """
        Reglas para subir/eliminar fotos.
        - Superuser / Super Admin SaaS: siempre.
        - Admin Empresa: siempre (DRAFT y CONFIRMED) dentro de su empresa.
        - Encargado / Empleado: solo si el cierre es DRAFT y de su sucursal.
        """
        is_global_admin = user.is_superuser or getattr(user, "is_super_admin_saas", False)
        if is_global_admin:
            return True

        # Debe pertenecer a la misma empresa del cierre
        if user.company_id != daily_cash.company_id:
            return False

        # Admin Empresa: puede en cualquier estado del cierre de su empresa
        if user.role == User.Role.ADMIN_COMPANY:
            return True

        # Encargado o Empleado: solo si es DRAFT y misma sucursal
        if daily_cash.status == DailyCash.Status.DRAFT:
            if user.branch_id == daily_cash.branch_id and user.role in [
                User.Role.BRANCH_MANAGER,
                User.Role.EMPLOYEE,
            ]:
                return True

        return False
    
    @action(detail=False, methods=["post"], url_path="create_with_photos")
    def create_with_photos(self, request):
        """
        Crea un cierre de caja y adjunta fotos en una sola operación.
        URL: POST /api/cash/daily/create_with_photos/
        """
        user = request.user

        is_global_admin = user.is_superuser or getattr(user, "is_super_admin_saas", False)

        # Permisos para crear DailyCash (igual que create normal)
        if user.role not in [User.Role.BRANCH_MANAGER, User.Role.ADMIN_COMPANY] and not is_global_admin:
            return Response(
                {
                    "status": "error",
                    "message": "No tiene permiso para crear cierres de caja.",
                },
                status=403,
            )

        data = request.data.copy()

        # ---- Encargado de sucursal ----
        if user.role == User.Role.BRANCH_MANAGER and not is_global_admin:
            if not user.company_id or not user.branch_id:
                return Response(
                    {
                        "status": "error",
                        "message": "El usuario debe tener empresa y sucursal asignadas.",
                    },
                    status=400,
                )
            data["company"] = user.company_id
            data["branch"] = user.branch_id

        # ---- Admin Empresa ----
        elif user.role == User.Role.ADMIN_COMPANY and not is_global_admin:
            if not user.company_id:
                return Response(
                    {
                        "status": "error",
                        "message": "El usuario debe tener empresa asignada.",
                    },
                    status=400,
                )
            if not data.get("branch"):
                return Response(
                    {
                        "status": "error",
                        "message": "Debe indicar la sucursal (branch) para el cierre.",
                    },
                    status=400,
                )
            data["company"] = user.company_id

        # ---- Superuser / Super Admin SaaS ----
        else:
            if not data.get("company") or not data.get("branch"):
                return Response(
                    {
                        "status": "error",
                        "message": "Debe indicar 'company' y 'branch' para el cierre.",
                    },
                    status=400,
                )

        # El status inicial lo dejamos (por defecto DRAFT en el modelo)
        # Creamos el cierre usando el serializer normal
        cash_serializer = DailyCashSerializer(data=data)
        if not cash_serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Datos inválidos para el cierre.",
                    "errors": cash_serializer.errors,
                },
                status=400,
            )

        daily_cash = cash_serializer.save()

        # Ahora manejamos las fotos
        files = request.FILES.getlist("photos")

        if files:
            # Validar permisos para fotos sobre el cierre recién creado
            if not self._can_manage_photos(user, daily_cash):
                return Response(
                    {
                        "status": "error",
                        "message": "No tiene permiso para adjuntar fotos a este cierre.",
                    },
                    status=403,
                )

            existing = daily_cash.photos.count()
            if existing + len(files) > self.MAX_PHOTOS_PER_CASH:
                remaining = max(self.MAX_PHOTOS_PER_CASH - existing, 0)
                return Response(
                    {
                        "status": "error",
                        "message": f"Solo se permiten {self.MAX_PHOTOS_PER_CASH} fotos por cierre. "
                                   f"Puede subir {remaining} más.",
                    },
                    status=400,
                )

            photo_serializer = DailyCashPhotoSerializer()

            for file in files:
                # Validar que sea imagen válida y <= 5MB
                photo_serializer.validate_image(file)

                # Comprimir a JPG calidad 70
                compressed = compress_image(file, quality=70, max_dim=2500)

                DailyCashPhoto.objects.create(daily_cash=daily_cash, image=compressed)

        # Devolvemos el cierre ya con photos incluidas
        return Response(
            {
                "status": "success",
                "message": "Cierre creado correctamente.",
                "data": DailyCashSerializer(daily_cash).data,
            },
            status=201,
        )



from rest_framework import serializers
from cash.models import DailyCash, DailyCashPhoto

class DailyCashPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyCashPhoto
        fields = ["id", "image", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

    def validate_image(self, value):
        # Extensiones permitidas
        valid_extensions = ["jpg", "jpeg", "png", "webp"]
        extension = value.name.split(".")[-1].lower()

        if extension not in valid_extensions:
            raise serializers.ValidationError(
                "Formato no permitido. Solo se aceptan JPG, JPEG, PNG, WEBP o HEIC."
            )

        # MIME types permitidos
        valid_mime = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/jpg"]
        content_type = getattr(value, "content_type", None)
        if content_type not in valid_mime:
            raise serializers.ValidationError("El archivo no es una imagen válida.")

        # Tamaño máximo 5 MB
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                "La imagen es muy grande. Máximo permitido: 5 MB."
            )

        return value


class DailyCashSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    closed_by_username = serializers.CharField(
        source="closed_by.username", read_only=True
    )
    total_by_payment_methods = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    # 👇 nuevo campo: lista de fotos asociadas al cierre
    photos = DailyCashPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = DailyCash
        fields = [
            "id",
            "company",
            "company_name",
            "branch",
            "branch_name",
            "date",
            "total_sales",
            "cash_amount",
            "card_amount",
            "qr_amount",
            "other_payments_amount",
            "extra_incomes",
            "extra_expenses",
            "difference",
            "status",
            "notes",
            "closed_by",
            "closed_by_username",
            "total_by_payment_methods",
            "photos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company_name",
            "branch_name",
            "closed_by",
            "closed_by_username",
            "total_by_payment_methods",
            "created_at",
            "updated_at",
        ]

from rest_framework import serializers

from orders.models import InternalOrder, InternalOrderItem


class InternalOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternalOrderItem
        fields = [
            "id",
            "description",
            "quantity",
            "unit",
            "notes",
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor que 0.")
        return value



class InternalOrderSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    items = InternalOrderItemSerializer(many=True)

    class Meta:
        model = InternalOrder
        fields = [
            "id",
            "company",
            "company_name",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",

            "status",
            "category",
            "priority",
            "comments",
            "purchasing_notes",

            "requested_date",
            "in_process_date",
            "sent_date",
            "delivered_date",
            "cancelled_date",

            "items",

            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company_name",
            "branch_name",
            "created_by_username",
            "requested_date",
            "in_process_date",
            "sent_date",
            "delivered_date",
            "cancelled_date",
            "created_at",
            "updated_at",
        ]

    # ---------- CREATE ----------
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = InternalOrder.objects.create(**validated_data)
        for item in items_data:
            InternalOrderItem.objects.create(order=order, **item)
        return order

    # ---------- UPDATE ----------
    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        # Campos simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Si vienen ítems, reemplazamos la lista completa
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                InternalOrderItem.objects.create(order=instance, **item)

        return instance

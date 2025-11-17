from django.db import models
from core.models import TimeStampedModel


class Company(TimeStampedModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Branch(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.company.name} - {self.name}"

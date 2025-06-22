from django.db import models
from django.utils import timezone


class WebhookTransaction(models.Model):
    STATUS_CHOICES = [
        ('received', 'Reçu'),
        ('processing', 'En traitement'),
        ('processed', 'Traité'),
        ('failed', 'Échoué'),
    ]

    transaction_id = models.CharField(max_length=255, unique=True)
    payload = models.JSONField()
    headers = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.status}"


class TransactionLog(models.Model):
    LOG_LEVELS = [
        ('info', 'Information'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur'),
        ('critical', 'Critique'),
    ]

    transaction = models.ForeignKey(WebhookTransaction, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(default=timezone.now)
    level = models.CharField(max_length=10, choices=LOG_LEVELS)
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.level}] {self.message[:50]}"
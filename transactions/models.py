from django.db import models
from django.conf import settings


# ✅ Main transaction model for legit messages
class Transaction(models.Model):
    reference_id = models.CharField(max_length=100, unique=True)
    network_provider = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    customer_name = models.CharField(max_length=100, null=True, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    transaction_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_transaction = models.DateTimeField()
    raw_sms = models.TextField()
    sender = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,related_name='transactions')
    is_incomplete = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.reference_id} - {self.type} - {self.amount}"


# ❌ Rejected SMS due to security or parsing issues
class RejectedSMS(models.Model):
    sender = models.CharField(max_length=100)
    message = models.TextField()
    reason = models.CharField(max_length=255)  # e.g., unknown sender, pattern mismatch
    received_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Rejected from {self.sender} at {self.received_at}"


from django.db import models

class Provider(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name



from django.contrib import admin
from .models import Transaction, RejectedSMS, Provider

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'amount', 'type', 'network_provider', 'user', 'date_transaction')

@admin.register(RejectedSMS)
class RejectedSMSAdmin(admin.ModelAdmin):
    list_display = ('sender', 'reason', 'received_at', 'user')

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')

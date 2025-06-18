
    
from rest_framework import serializers
from .models import Transaction
from .models import Provider

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'

class RawSMSSerializer(serializers.Serializer):
    sms_text = serializers.CharField()

class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = '__all__'


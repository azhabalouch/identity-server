from rest_framework import serializers
from gateway.serializers import StrictSerializer

from .constants import CONTEXT_CHOICES, VISIBILITY_CHOICES
from .models import ContextualName

class AttributeWriteSerializer(StrictSerializer):
    attribute_key = serializers.CharField(max_length=64)
    attribute_value = serializers.CharField(max_length=500, allow_null=True, 
    allow_blank=False)
    visibility_level = serializers.ChoiceField(choices=VISIBILITY_CHOICES, required=False)

class PersonaPatchSerializer(StrictSerializer):
    attributes = serializers.ListField(child=AttributeWriteSerializer(), min_length=1, max_length=50)

class NameWriteSerializer(StrictSerializer):
    name_value = serializers.CharField(max_length=150)
    name_type = serializers.ChoiceField(choices=ContextualName.NAME_TYPES)
    context = serializers.ChoiceField(choices=CONTEXT_CHOICES)
    visibility_level = serializers.ChoiceField(choices=VISIBILITY_CHOICES, required=False)
    is_default = serializers.BooleanField(required=False)
    valid_from = serializers.DateField(required=False, allow_null=True)
    valid_to = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        start, end = attrs.get("valid_from"), attrs.get("valid_to")

        if start and end and end < start:
            raise serializers.ValidationError({"valid_to": ["must be on or after valid_from"]})
        
        return attrs
    
def attribute_json(row):
    return {
        "attribute_key": row.attribute_key_id,
        "label": row.attribute_key.label,
        "attribute_value": row.attribute_value,
        "visibility_level": row.visibility_level,
    }

def name_json(row):
    return {
        "id": row.id,
        "name_value": row.name_value,
        "name_type": row.name_type,
        "context": row.context,
        "visibility_level": row.visibility_level,
        "is_default": row.is_default,
        "valid_from": row.valid_from,
        "valid_to": row.valid_to,
    }
from rest_framework import serializers

class StrictSerializer(serializers.Serializer):
    """Reject unexpected fields instead of ignoring them (mass assignment defence)."""

    def to_internal_value(self, data):
        unknown = []

        if hasattr(data, "keys"):
            unknown = sorted(set(data.keys()) - set(self.fields))
            
        if unknown:
            raise serializers.ValidationError({"non_field_errors": [f"unexpected field(s): {', '.join(unknown)}"]})
        
        return super().to_internal_value(data)
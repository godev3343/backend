from rest_framework import serializers


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class EmptySerializer(serializers.Serializer):
    pass


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField(required=False)


class ReadinessSerializer(serializers.Serializer):
    status = serializers.CharField()
    db = serializers.BooleanField()
    redis = serializers.BooleanField()
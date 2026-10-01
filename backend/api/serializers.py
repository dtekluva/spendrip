from rest_framework import serializers

from drips.models import Plan, Recipient, Run


class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = ["id", "label", "is_self", "bank_name", "nip_bank_code", "account_number", "verified_account_name", "whatsapp", "notify_whatsapp"]


class PlanSerializer(serializers.ModelSerializer):
    recipient = RecipientSerializer(read_only=True)

    class Meta:
        model = Plan
        fields = ["id", "label", "emoji", "tint", "amount_kobo", "recipient", "frequency", "weekday", "month_day", "month_day_last",
                  "time_local", "tz", "starts_at", "ends_at", "status", "priority_rank"]


class RunSerializer(serializers.ModelSerializer):
    plan_label = serializers.CharField(source="plan.label")
    plan_emoji = serializers.CharField(source="plan.emoji")

    class Meta:
        model = Run
        fields = ["id", "plan", "plan_label", "plan_emoji", "scheduled_for", "amount_kobo", "fee_kobo", "status", "completed_at"]

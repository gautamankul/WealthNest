from django.contrib.auth.models import User
from django.db import models


class Asset(models.Model):
    """
    Asset type (Mutual Funds, Gold, ...). Table: assets.

    created_by is NULL  -> default asset shared by every user
    created_by is a user -> custom asset visible only to that user
    """

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="created_assets",
    )
    name = models.CharField(max_length=30)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "name"],
                name="unique_user_asset_name",
            )
        ]

    def __str__(self):
        return self.name


class Investment(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_investments",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="updated_investments",
    )

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="investments",
    )
    name = models.CharField(max_length=200)
    purchase_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    invested_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    current_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def profit_loss(self):
        return self.current_value - self.invested_amount

    @property
    def return_pct(self):
        return (
            self.profit_loss / self.invested_amount * 100
            if self.invested_amount
            else 0
        )


class MonthlyContribution(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_monthly_contributions",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="updated_monthly_contributions",
    )

    month = models.DateField(help_text="First day of month")
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="monthly_contributions",
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "month", "asset"],
                name="unique_user_month_asset",
            )
        ]
        ordering = ["-month", "asset"]


class AllocationTarget(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_allocation_targets",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="updated_allocation_targets",
    )

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="allocation_targets",
    )
    target_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "asset"],
                name="unique_user_asset_target",
            )
        ]
        ordering = ["asset"]


class Goal(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_goals",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="updated_goals",
    )

    name = models.CharField(max_length=200)
    target_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )
    current_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    target_date = models.DateField()
    monthly_contribution = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
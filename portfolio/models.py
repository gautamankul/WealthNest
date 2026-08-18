from django.db import models

ASSET_CHOICES=[('Mutual Funds','Mutual Funds'),('Gold','Gold'),('Silver','Silver'),('Bonds','Bonds'),('Other','Other')]

class Investment(models.Model):
    asset=models.CharField(max_length=30,choices=ASSET_CHOICES)
    name=models.CharField(max_length=200)
    purchase_date=models.DateField(null=True,blank=True)
    quantity=models.DecimalField(max_digits=18,decimal_places=4,null=True,blank=True)
    invested_amount=models.DecimalField(max_digits=15,decimal_places=2,default=0)
    current_value=models.DecimalField(max_digits=15,decimal_places=2,default=0)
    notes=models.TextField(blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    @property
    def profit_loss(self): return self.current_value-self.invested_amount
    @property
    def return_pct(self): return (self.profit_loss/self.invested_amount*100) if self.invested_amount else 0

class MonthlyContribution(models.Model):
    month=models.DateField(help_text='First day of month')
    asset=models.CharField(max_length=30,choices=ASSET_CHOICES)
    amount=models.DecimalField(max_digits=15,decimal_places=2,default=0)
    class Meta:
        unique_together=('month','asset')
        ordering=['-month','asset']

class AllocationTarget(models.Model):
    asset=models.CharField(max_length=30,choices=ASSET_CHOICES,unique=True)
    target_pct=models.DecimalField(max_digits=5,decimal_places=2,default=0)
    class Meta: ordering=['asset']

class Goal(models.Model):
    name=models.CharField(max_length=200)
    target_amount=models.DecimalField(max_digits=15,decimal_places=2)
    current_amount=models.DecimalField(max_digits=15,decimal_places=2,default=0)
    target_date=models.DateField()
    monthly_contribution=models.DecimalField(max_digits=15,decimal_places=2,default=0)

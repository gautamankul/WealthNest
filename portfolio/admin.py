from django.contrib import admin
from .models import Investment,MonthlyContribution,AllocationTarget,Goal
admin.site.register(Investment)
admin.site.register(MonthlyContribution)
admin.site.register(AllocationTarget)
admin.site.register(Goal)

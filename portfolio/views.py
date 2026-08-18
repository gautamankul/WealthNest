from datetime import date,datetime
from decimal import Decimal
import csv, io
from django.http import JsonResponse,HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from .models import Investment,MonthlyContribution,AllocationTarget,Goal,ASSET_CHOICES

ASSETS=[x[0] for x in ASSET_CHOICES]
def f(x): return float(x or 0)
def money(x): return f(x)

def seed_if_empty():
    if not Investment.objects.exists():
        rows=[('Mutual Funds','Mutual Funds',720000,809000),('Gold','Gold',330000,386000),('Silver','Silver',150000,190000),('Bonds','Bonds',250000,273000),('Other','Other',75000,90750)]
        Investment.objects.bulk_create([Investment(asset=a,name=n,invested_amount=i,current_value=v) for a,n,i,v in rows])
    if not AllocationTarget.objects.exists():
        AllocationTarget.objects.bulk_create([AllocationTarget(asset=a,target_pct=p) for a,p in [('Mutual Funds',45),('Gold',20),('Silver',10),('Bonds',20),('Other',5)]])
    if not MonthlyContribution.objects.exists():
        vals={('2026-01','Mutual Funds'):25000,('2026-01','Gold'):5000,('2026-01','Other'):5000,('2026-02','Mutual Funds'):25000,('2026-02','Gold'):5000,('2026-02','Other'):5000,('2026-03','Mutual Funds'):30000,('2026-03','Gold'):5000,('2026-03','Other'):5000,('2026-04','Mutual Funds'):25000,('2026-04','Gold'):5000,('2026-04','Bonds'):3000,('2026-04','Other'):5000,('2026-05','Mutual Funds'):25000,('2026-05','Gold'):5000,('2026-05','Bonds'):3000,('2026-05','Other'):5000,('2026-06','Mutual Funds'):30000,('2026-06','Gold'):5000,('2026-06','Silver'):2000,('2026-06','Bonds'):3000,('2026-06','Other'):5000,('2026-07','Mutual Funds'):25000,('2026-07','Gold'):5000,('2026-07','Silver'):2000,('2026-07','Bonds'):3000,('2026-07','Other'):5000,('2026-08','Mutual Funds'):25000,('2026-08','Gold'):5000,('2026-08','Silver'):2000,('2026-08','Bonds'):3000,('2026-08','Other'):5000}
        for (m,a),v in vals.items(): MonthlyContribution.objects.create(month=datetime.strptime(m+'-01','%Y-%m-%d').date(),asset=a,amount=v)
    if not Goal.objects.exists():
        Goal.objects.create(name='Buy House',target_amount=5000000,current_amount=2600000,target_date='2030-12-31',monthly_contribution=35000)
        Goal.objects.create(name='Retirement Fund',target_amount=10000000,current_amount=2800000,target_date='2040-12-31',monthly_contribution=35000)

def payload():
    seed_if_empty()
    inv=list(Investment.objects.all())
    total_i=sum((x.invested_amount for x in inv),Decimal(0)); total_v=sum((x.current_value for x in inv),Decimal(0)); profit=total_v-total_i
    targets={x.asset:f(x.target_pct) for x in AllocationTarget.objects.all()}
    allocation=[]
    for a in ASSETS:
        ai=sum((x.invested_amount for x in inv if x.asset==a),Decimal(0)); av=sum((x.current_value for x in inv if x.asset==a),Decimal(0)); p=av-ai; cur=f(av/total_v*100) if total_v else 0; tgt=targets.get(a,0)
        allocation.append({'asset':a,'invested':f(ai),'value':f(av),'profit_loss':f(p),'return_pct':f(p/ai*100) if ai else 0,'current_pct':cur,'target_pct':tgt,'difference_pct':cur-tgt})
    monthly=list(MonthlyContribution.objects.all())
    months={}
    for x in monthly: months.setdefault(x.month.isoformat()[:7],{}); months[x.month.isoformat()[:7]][x.asset]=f(x.amount)
    monthly_series=[{'month':m,'total':sum(v.values()),'by_asset':v} for m,v in sorted(months.items())]
    current_month=date.today().strftime('%Y-%m')
    # show Aug 2026 sample if today's data is absent
    if not any(x['month']==current_month for x in monthly_series): current_month=monthly_series[-1]['month'] if monthly_series else current_month
    monthly_total=next((x['total'] for x in monthly_series if x['month']==current_month),0)
    annual_total=sum(x['total'] for x in monthly_series if x['month'].startswith(str(date.today().year)))
    # suggested next allocation uses the user's target percentages and current value
    suggested=[]
    for x in allocation:
        need=max(0,(x['target_pct']/100*float(total_v))-x['value'])
        suggested.append({'asset':x['asset'],'amount_needed':need})
    goals=[]
    for g in Goal.objects.all():
        months_left=max(0,(g.target_date.year-date.today().year)*12+g.target_date.month-date.today().month)
        projected=f(g.current_amount)+f(g.monthly_contribution)*months_left
        goals.append({'id':g.id,'name':g.name,'target_amount':f(g.target_amount),'current_amount':f(g.current_amount),'target_date':g.target_date.isoformat(),'monthly_contribution':f(g.monthly_contribution),'progress_pct':f(g.current_amount/g.target_amount*100) if g.target_amount else 0,'projected_amount':projected,'on_track':projected>=f(g.target_amount)})
    return {'total_invested':f(total_i),'current_value':f(total_v),'profit_loss':f(profit),'return_pct':f(profit/total_i*100) if total_i else 0,'allocation':allocation,'monthly_series':monthly_series,'current_month':current_month,'monthly_total':monthly_total,'annual_total':annual_total,'suggested':suggested,'goals':goals,'projection':{'conservative':f(total_v*Decimal('1.05')),'expected':f(total_v*Decimal('1.10')),'optimistic':f(total_v*Decimal('1.16'))}}

def dashboard(request): return render(request,'portfolio/dashboard.html')
def reports(request): return render(request,'portfolio/reports.html')
def dashboard_api(request): return JsonResponse(payload())

@require_http_methods(['POST'])
def investment_api(request):
    d=request.POST
    asset=d.get('asset')
    name=d.get('name')
    if not asset or not name:
        return JsonResponse({'ok':False,'error':'Asset and investment name are required.'},status=400)
    obj=Investment.objects.create(
        asset=asset,
        name=name,
        purchase_date=d.get('purchase_date') or None,
        invested_amount=Decimal(d.get('invested_amount') or 0),
        current_value=Decimal(d.get('current_value') or 0),
        notes=d.get('notes','')
    )
    return JsonResponse({'id':obj.id,'ok':True})

@require_http_methods(['POST'])
def monthly_api(request):
    d=request.POST
    month_value=d.get('month')
    if not month_value:
        return JsonResponse({'ok':False,'error':'Month is required.'},status=400)
    try:
        month=datetime.strptime(month_value+'-01','%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'ok':False,'error':'Invalid month. Please use YYYY-MM.'},status=400)
    for a in ASSETS:
        amount=Decimal(d.get(a,'0') or 0)
        MonthlyContribution.objects.update_or_create(month=month,asset=a,defaults={'amount':amount})
    return JsonResponse({'ok':True})

@require_http_methods(['POST'])
def targets_api(request):
    total=Decimal('0')
    values={}
    for a in ASSETS:
        value=Decimal(request.POST.get(a,'0') or 0)
        if value < 0:
            return JsonResponse({'ok':False,'error':'Allocation percentages cannot be negative.'},status=400)
        values[a]=value
        total += value
    if total != Decimal('100'):
        return JsonResponse({'ok':False,'error':f'Target allocation must total 100%. Current total: {total}%.'},status=400)
    for a,value in values.items():
        AllocationTarget.objects.update_or_create(asset=a,defaults={'target_pct':value})
    return JsonResponse({'ok':True})

@require_http_methods(['POST'])
def goal_api(request):
    d=request.POST
    required=['name','target_amount','target_date']
    missing=[x for x in required if not d.get(x)]
    if missing:
        return JsonResponse({'ok':False,'error':'Missing required field(s): '+', '.join(missing)},status=400)
    Goal.objects.create(
        name=d.get('name'),
        target_amount=Decimal(d.get('target_amount') or 0),
        current_amount=Decimal(d.get('current_amount') or 0),
        target_date=d.get('target_date'),
        monthly_contribution=Decimal(d.get('monthly_contribution') or 0)
    )
    return JsonResponse({'ok':True})

def report_api(request):
    seed_if_empty(); start=request.GET.get('start'); end=request.GET.get('end')
    qs=MonthlyContribution.objects.all()
    if start: qs=qs.filter(month__gte=start+'-01')
    if end: qs=qs.filter(month__lte=end+'-01')
    data={}
    for x in qs: data.setdefault(x.month.isoformat()[:7],{a:0 for a in ASSETS})[x.asset]=f(x.amount)
    rows=[{'month':m,**v,'total':sum(v.values())} for m,v in sorted(data.items())]
    return JsonResponse({'rows':rows,'total':sum(x['total'] for x in rows)})

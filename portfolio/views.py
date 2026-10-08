from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import (
    Asset,
    Investment,
    MonthlyContribution,
    AllocationTarget,
    Goal,
)

# Scenario annual returns (match the +5% / +10% / +16% labels in the UI)
SCENARIOS = {
    "conservative": Decimal("0.05"),
    "expected": Decimal("0.10"),
    "optimistic": Decimal("0.16"),
}
GOAL_ANNUAL_RETURN = Decimal("0.10")

# Only used to pre-fill the Target modal when the user has no saved targets
DEFAULT_TARGETS = {
    "Mutual Funds": 45,
    "Gold": 20,
    "Silver": 10,
    "Bonds": 20,
    "Other": 5,
}


# ============================================================
# HELPERS
# ============================================================


def f(x):
    return float(x or 0)


def money(x):
    return f(x)


# Names that would collide with other form fields
RESERVED_ASSET_NAMES = {"month", "asset", "name", "csrfmiddlewaretoken"}


def visible_assets(user):
    """Default assets (created_by NULL) + the user's own custom assets."""
    return Asset.objects.filter(Q(created_by__isnull=True) | Q(created_by=user))


def get_assets(user):
    """Assets this user can use, ordered by sort_order, name."""
    return list(visible_assets(user))


def resolve_asset(value, user):
    """Accept an Asset id or name; only returns assets visible to the user."""
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    qs = visible_assets(user)

    if value.isdigit():
        obj = qs.filter(pk=int(value)).first()
        if obj:
            return obj

    return qs.filter(name=value).first()


def parse_decimal(value, default="0"):
    """Return Decimal or None if the value is not a valid number."""
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, ValueError):
        return None


def future_value(present, monthly, annual_rate, months):
    """Compound monthly: future value of a lump sum plus monthly contributions."""
    present = Decimal(present or 0)
    monthly = Decimal(monthly or 0)

    if months <= 0:
        return present

    r = (Decimal(1) + annual_rate) ** (Decimal(1) / 12) - 1
    growth = (Decimal(1) + r) ** months
    return present * growth + monthly * ((growth - 1) / r)


def avg_recent_monthly(monthly_series, n=3):
    """Average of the last n months of contributions."""
    recent = [x["total"] for x in monthly_series[-n:]]
    return sum(recent) / len(recent) if recent else 0


def split_budget(allocation, budget, total_value):
    """
    Split `budget` across assets that are below target, measured against
    the portfolio value AFTER adding the budget.
    """
    new_total = total_value + budget

    gaps = {}
    for x in allocation:
        want = x["target_pct"] / 100 * new_total
        gaps[x["asset"]] = max(0, want - x["value"])

    gap_sum = sum(gaps.values())

    out = []
    for x in allocation:
        if budget <= 0 or gap_sum <= 0:
            amt = 0
        else:
            amt = budget * gaps[x["asset"]] / gap_sum

        out.append(
            {
                "asset": x["asset"],
                "amount_needed": round(amt, 2),
            }
        )

    return out


def sync_contribution_holdings(user):
    """
    Make each 'Monthly contributions – <asset>' holding's invested amount
    equal the sum of all saved monthly contributions for that asset.
    Any difference is added to current_value (valued at cost).
    Self-healing: safe to call any time, also backfills old months.
    """
    totals = {
        row["asset"]: row["total"] or Decimal(0)
        for row in MonthlyContribution.objects.filter(created_by=user)
        .order_by()
        .values("asset")
        .annotate(total=Sum("amount"))
    }

    for asset in get_assets(user):
        total = totals.get(asset.id, Decimal(0))

        holding = Investment.objects.filter(
            created_by=user,
            asset=asset,
            name=f"Monthly contributions – {asset.name}",
        ).first()

        if holding is None:
            if total == 0:
                continue  # nothing to track yet

            holding = Investment.objects.create(
                created_by=user,
                updated_by=user,
                asset=asset,
                name=f"Monthly contributions – {asset.name}",
                invested_amount=0,
                current_value=0,
            )

        diff = total - holding.invested_amount

        if diff != 0:
            holding.invested_amount += diff
            holding.current_value += diff
            holding.updated_by = user
            holding.save()


# ============================================================
# DASHBOARD PAYLOAD
# ============================================================


def payload(user):

    assets = get_assets(user)

    # --------------------------------------------------------
    # INVESTMENTS
    # --------------------------------------------------------

    inv = list(Investment.objects.filter(created_by=user))

    total_i = sum((x.invested_amount for x in inv), Decimal(0))
    total_v = sum((x.current_value for x in inv), Decimal(0))
    profit = total_v - total_i

    # --------------------------------------------------------
    # ALLOCATION
    # --------------------------------------------------------

    targets = {
        x.asset_id: f(x.target_pct)
        for x in AllocationTarget.objects.filter(created_by=user)
    }

    allocation = []

    for a in assets:
        ai = sum((x.invested_amount for x in inv if x.asset_id == a.id), Decimal(0))
        av = sum((x.current_value for x in inv if x.asset_id == a.id), Decimal(0))

        p = av - ai
        cur = f(av / total_v * 100) if total_v else 0
        tgt = targets.get(a.id, 0)

        allocation.append(
            {
                "asset": a.name,
                "asset_id": a.id,
                "invested": f(ai),
                "value": f(av),
                "profit_loss": f(p),
                "return_pct": f(p / ai * 100) if ai else 0,
                "current_pct": cur,
                "target_pct": tgt,
                "difference_pct": cur - tgt,
            }
        )

    # --------------------------------------------------------
    # MONTHLY CONTRIBUTIONS
    # --------------------------------------------------------

    months = {}

    for x in MonthlyContribution.objects.filter(created_by=user).select_related("asset"):
        month_key = x.month.isoformat()[:7]
        months.setdefault(month_key, {})
        months[month_key][x.asset.name] = f(x.amount)

    monthly_series = [
        {
            "month": m,
            "total": sum(v.values()),
            "by_asset": v,
        }
        for m, v in sorted(months.items())
    ]

    # --------------------------------------------------------
    # CURRENT MONTH
    # --------------------------------------------------------

    current_month = date.today().strftime("%Y-%m")

    if not any(x["month"] == current_month for x in monthly_series):
        current_month = monthly_series[-1]["month"] if monthly_series else current_month

    monthly_total = next(
        (x["total"] for x in monthly_series if x["month"] == current_month),
        0,
    )

    # --------------------------------------------------------
    # ANNUAL CONTRIBUTION
    # --------------------------------------------------------

    year = str(date.today().year)

    annual_total = sum(x["total"] for x in monthly_series if x["month"].startswith(year))

    # --------------------------------------------------------
    # NEXT MONTHLY ALLOCATION (budget = avg of last 3 months)
    # --------------------------------------------------------

    next_budget = avg_recent_monthly(monthly_series, 3)

    suggested = split_budget(allocation, next_budget, f(total_v))

    # --------------------------------------------------------
    # GOALS
    # --------------------------------------------------------

    today = date.today()

    goals = []

    for g in Goal.objects.filter(created_by=user):

        months_left = max(
            0,
            (g.target_date.year - today.year) * 12 + g.target_date.month - today.month,
        )

        projected = future_value(
            g.current_amount,
            g.monthly_contribution,
            GOAL_ANNUAL_RETURN,
            months_left,
        )

        goals.append(
            {
                "id": g.id,
                "name": g.name,
                "target_amount": f(g.target_amount),
                "current_amount": f(g.current_amount),
                "target_date": g.target_date.isoformat(),
                "monthly_contribution": f(g.monthly_contribution),
                "progress_pct": (
                    f(g.current_amount / g.target_amount * 100)
                    if g.target_amount
                    else 0
                ),
                "projected_amount": f(projected),
                "on_track": projected >= g.target_amount,
            }
        )

    # --------------------------------------------------------
    # 1-YEAR PROJECTION (current value + future contributions)
    # --------------------------------------------------------

    monthly_dec = Decimal(str(round(next_budget, 2)))

    projection = {
        k: f(future_value(total_v, monthly_dec, rate, 12))
        for k, rate in SCENARIOS.items()
    }

    # --------------------------------------------------------
    # FINAL PAYLOAD
    # --------------------------------------------------------

    return {
        "assets": [{"id": a.id, "name": a.name} for a in assets],
        "total_invested": f(total_i),
        "current_value": f(total_v),
        "profit_loss": f(profit),
        "return_pct": f(profit / total_i * 100) if total_i else 0,
        "allocation": allocation,
        "monthly_series": monthly_series,
        "current_month": current_month,
        "monthly_total": monthly_total,
        "annual_total": annual_total,
        "suggested": suggested,
        "next_budget": next_budget,
        "goals": goals,
        "projection": projection,
    }


# ============================================================
# DASHBOARD API
# ============================================================


@login_required
def dashboard_api(request):

    return JsonResponse(payload(request.user))


# ============================================================
# ASSET APIs (user creates / deletes own assets)
# ============================================================


@login_required
@require_http_methods(["POST"])
def asset_api(request):

    name = " ".join((request.POST.get("name") or "").split())

    if not name:
        return JsonResponse(
            {"ok": False, "error": "Asset name is required."},
            status=400,
        )

    if len(name) > 30:
        return JsonResponse(
            {"ok": False, "error": "Asset name must be 30 characters or fewer."},
            status=400,
        )

    if name.lower() in RESERVED_ASSET_NAMES:
        return JsonResponse(
            {"ok": False, "error": "This name is reserved. Choose another."},
            status=400,
        )

    qs = visible_assets(request.user)

    if qs.filter(name__iexact=name).exists():
        return JsonResponse(
            {"ok": False, "error": "You already have an asset with this name."},
            status=400,
        )

    last = qs.aggregate(m=Max("sort_order"))["m"] or 0

    asset = Asset.objects.create(
        created_by=request.user,
        name=name,
        sort_order=last + 1,
    )

    return JsonResponse({"ok": True, "id": asset.id, "name": asset.name})


@login_required
@require_http_methods(["POST"])
def asset_delete_api(request, pk):

    asset = visible_assets(request.user).filter(pk=pk).first()

    if asset is None:
        return JsonResponse({"ok": False, "error": "Not found."}, status=404)

    if asset.created_by_id is None:
        return JsonResponse(
            {"ok": False, "error": "Default assets cannot be deleted."},
            status=400,
        )

    holdings = Investment.objects.filter(created_by=request.user, asset=asset)
    contributions = MonthlyContribution.objects.filter(
        created_by=request.user, asset=asset
    )

    has_money = (
        holdings.exclude(invested_amount=0, current_value=0).exists()
        or contributions.exclude(amount=0).exists()
    )

    if has_money:
        return JsonResponse(
            {
                "ok": False,
                "error": "This asset has investments or contributions and cannot be deleted.",
            },
            status=400,
        )

    with transaction.atomic():
        holdings.delete()
        contributions.delete()
        AllocationTarget.objects.filter(
            created_by=request.user, asset=asset
        ).delete()
        asset.delete()

    return JsonResponse({"ok": True})


# ============================================================
# INVESTMENT API
# ============================================================


@login_required
@require_http_methods(["POST"])
def investment_api(request):

    d = request.POST

    name = d.get("name")
    asset = resolve_asset(d.get("asset"), request.user)

    if not d.get("asset") or not name:
        return JsonResponse(
            {
                "ok": False,
                "error": "Asset and investment name are required.",
            },
            status=400,
        )

    if asset is None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid asset type.",
            },
            status=400,
        )

    invested_amount = parse_decimal(d.get("invested_amount"))
    current_value = parse_decimal(d.get("current_value"))
    quantity = parse_decimal(d.get("quantity"))

    if invested_amount is None or current_value is None or quantity is None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid numeric value.",
            },
            status=400,
        )

    if invested_amount < 0 or current_value < 0 or quantity < 0:
        return JsonResponse(
            {
                "ok": False,
                "error": "Values cannot be negative.",
            },
            status=400,
        )

    obj = Investment.objects.create(
        created_by=request.user,
        updated_by=request.user,
        asset=asset,
        name=name,
        purchase_date=(d.get("purchase_date") or None),
        quantity=quantity,
        invested_amount=invested_amount,
        current_value=current_value,
        notes=d.get("notes", ""),
    )

    return JsonResponse(
        {
            "id": obj.id,
            "ok": True,
        }
    )


# ============================================================
# HOLDING VALUE API (update market value of a holding)
# ============================================================


@login_required
@require_http_methods(["POST"])
def holding_value_api(request, pk):

    value = parse_decimal(request.POST.get("current_value"), default="")

    if value is None or value < 0:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid value.",
            },
            status=400,
        )

    updated = Investment.objects.filter(
        pk=pk,
        created_by=request.user,
    ).update(
        current_value=value,
        updated_by=request.user,
    )

    if not updated:
        return JsonResponse(
            {
                "ok": False,
                "error": "Not found.",
            },
            status=404,
        )

    return JsonResponse({"ok": True})


# ============================================================
# MONTHLY CONTRIBUTION API (syncs into holdings)
# ============================================================


@login_required
@require_http_methods(["POST"])
def monthly_api(request):

    d = request.POST

    month_value = d.get("month")

    if not month_value:
        return JsonResponse(
            {
                "ok": False,
                "error": "Month is required.",
            },
            status=400,
        )

    try:
        month = datetime.strptime(month_value + "-01", "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid month. Please use YYYY-MM.",
            },
            status=400,
        )

    assets = get_assets(request.user)

    # Validate everything first so a partial month is never saved.
    # Form fields are named after the asset (name="Gold") or its id (name="2").
    amounts = {}

    for a in assets:
        raw = d.get(a.name)
        if raw is None:
            raw = d.get(str(a.id))

        amount = parse_decimal(raw)

        if amount is None:
            return JsonResponse(
                {
                    "ok": False,
                    "error": f"Invalid amount for {a.name}.",
                },
                status=400,
            )

        if amount < 0:
            return JsonResponse(
                {
                    "ok": False,
                    "error": f"Amount for {a.name} cannot be negative.",
                },
                status=400,
            )

        amounts[a] = amount

    with transaction.atomic():

        for a, amount in amounts.items():
            MonthlyContribution.objects.update_or_create(
                created_by=request.user,
                month=month,
                asset=a,
                defaults={
                    "amount": amount,
                    "updated_by": request.user,
                },
            )

        sync_contribution_holdings(request.user)

    return JsonResponse({"ok": True})


# ============================================================
# ALLOCATION TARGET API
# ============================================================


@login_required
@require_http_methods(["POST"])
def targets_api(request):

    total = Decimal("0")

    values = {}

    for a in get_assets(request.user):

        raw = request.POST.get(a.name)
        if raw is None:
            raw = request.POST.get(str(a.id))

        value = parse_decimal(raw)

        if value is None:
            return JsonResponse(
                {
                    "ok": False,
                    "error": f"Invalid percentage for {a.name}.",
                },
                status=400,
            )

        if value < 0:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Allocation percentages cannot be negative.",
                },
                status=400,
            )

        values[a] = value
        total += value

    if total != Decimal("100"):
        return JsonResponse(
            {
                "ok": False,
                "error": f"Target allocation must total 100%. Current total: {total}%.",
            },
            status=400,
        )

    with transaction.atomic():
        for a, value in values.items():
            AllocationTarget.objects.update_or_create(
                created_by=request.user,
                asset=a,
                defaults={
                    "target_pct": value,
                    "updated_by": request.user,
                },
            )

    return JsonResponse({"ok": True})


# ============================================================
# GOAL API
# ============================================================


@login_required
@require_http_methods(["POST"])
def goal_api(request):

    d = request.POST

    required = [
        "name",
        "target_amount",
        "target_date",
    ]

    missing = [x for x in required if not d.get(x)]

    if missing:
        return JsonResponse(
            {
                "ok": False,
                "error": "Missing required field(s): " + ", ".join(missing),
            },
            status=400,
        )

    target_amount = parse_decimal(d.get("target_amount"))
    current_amount = parse_decimal(d.get("current_amount"))
    monthly_contribution = parse_decimal(d.get("monthly_contribution"))

    if target_amount is None or current_amount is None or monthly_contribution is None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid numeric value.",
            },
            status=400,
        )

    if target_amount <= 0 or current_amount < 0 or monthly_contribution < 0:
        return JsonResponse(
            {
                "ok": False,
                "error": "Amounts must be positive.",
            },
            status=400,
        )

    try:
        target_date = datetime.strptime(d.get("target_date"), "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid target date.",
            },
            status=400,
        )

    goal = Goal.objects.create(
        created_by=request.user,
        updated_by=request.user,
        name=d.get("name"),
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=target_date,
        monthly_contribution=monthly_contribution,
    )

    return JsonResponse(
        {
            "ok": True,
            "id": goal.id,
        }
    )


# ============================================================
# REPORT API
# ============================================================


@login_required
def report_api(request):

    start = request.GET.get("start")
    end = request.GET.get("end")

    assets = get_assets(request.user)

    qs = MonthlyContribution.objects.filter(created_by=request.user).select_related(
        "asset"
    )

    if start:
        qs = qs.filter(month__gte=start + "-01")

    if end:
        qs = qs.filter(month__lte=end + "-01")

    data = {}

    for x in qs:
        month_key = x.month.isoformat()[:7]

        data.setdefault(
            month_key,
            {a.name: 0 for a in assets},
        )

        data[month_key][x.asset.name] = f(x.amount)

    rows = [
        {
            "month": m,
            **v,
            "total": sum(v.values()),
        }
        for m, v in sorted(data.items())
    ]

    return JsonResponse(
        {
            "assets": [a.name for a in assets],
            "rows": rows,
            "total": sum(x["total"] for x in rows),
        }
    )


# ============================================================
# PAGES
# ============================================================


@login_required
def dashboard(request):

    # Backfill: make sure saved months are reflected in holdings
    with transaction.atomic():
        sync_contribution_holdings(request.user)

    data = payload(request.user)

    saved_targets = {
        t.asset_id: f(t.target_pct)
        for t in AllocationTarget.objects.filter(created_by=request.user)
    }

    asset_rows = [
        {
            "id": a.id,
            "name": a.name,
            "index": i,
            "is_custom": a.created_by_id is not None,
            "target": saved_targets.get(
                a.id, DEFAULT_TARGETS.get(a.name, 0) if a.created_by_id is None else 0
            ),
        }
        for i, a in enumerate(get_assets(request.user), start=1)
    ]

    return render(
        request,
        "portfolio/dashboard.html",
        {
            "assets": asset_rows,
            "next_budget": round(data["next_budget"]),
        },
    )


@login_required
def reports(request):

    return render(
        request,
        "portfolio/reports.html",
        {
            "assets": get_assets(request.user),
        },
    )
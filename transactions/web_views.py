from django.shortcuts import render
from .models import Transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta

def dashboard_view(request):
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    totals = {
        "today": Transaction.objects.filter(date_transaction__date=today).count(),
        "week": Transaction.objects.filter(date_transaction__date__gte=week_start).count(),
        "month": Transaction.objects.filter(date_transaction__date__gte=month_start).count(),
        "year": Transaction.objects.filter(date_transaction__date__gte=year_start).count(),
    }

    providers = (
        Transaction.objects
        .values("network_provider")
        .annotate(total=Count("id"))
        .order_by("network_provider")
    )

    total_all = Transaction.objects.count()
    context = {
        "totals": totals,
        "providers": providers,
        "total_all": total_all
    }
    return render(request, "transactions/dashboard.html", context)



def provider_transactions_view(request, provider):
    query = request.GET.get("q", "")
    page = request.GET.get("page", 1)

    filtered = Transaction.objects.filter(network_provider__iexact=provider)

    if query:
        filtered = filtered.filter(
            Q(reference_id__icontains=query) |
            Q(customer_phone__icontains=query) |
            Q(type__icontains=query)
        )

    paginator = Paginator(filtered.order_by('-date_transaction'), 10)  # 10 per page
    transactions = paginator.get_page(page)

    return render(request, 'transactions/provider_transactions.html', {
        'provider': provider.upper(),
        'transactions': transactions,
        'query': query
    })



def all_transactions_view(request):
    query = request.GET.get("q", "")
    provider = request.GET.get("provider", "")
    txn_type = request.GET.get("type", "")
    page = request.GET.get("page", 1)

    transactions = Transaction.objects.all()

    if query:
        transactions = transactions.filter(
            Q(reference_id__icontains=query) |
            Q(customer_phone__icontains=query) |
            Q(customer_name__icontains=query)
        )
    if provider:
        transactions = transactions.filter(network_provider__iexact=provider)
    if txn_type:
        transactions = transactions.filter(type__iexact=txn_type)

    transactions = transactions.order_by("-date_transaction")
    paginator = Paginator(transactions, 10)
    paginated = paginator.get_page(page)

    providers = Transaction.objects.values_list("network_provider", flat=True).distinct()
    types = Transaction.objects.values_list("type", flat=True).distinct()

    return render(request, "transactions/all_sms.html", {
        "transactions": paginated,
        "providers": providers,
        "types": types,
        "query": query,
        "selected_provider": provider,
        "selected_type": txn_type
    })

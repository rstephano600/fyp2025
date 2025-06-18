from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status, generics
from .models import Transaction, RejectedSMS, Provider
from .serializers import TransactionSerializer, ProviderSerializer
from sms_parser.parser import parse_sms
from utils.sms_handler import handle_sms_submission
from django.db.models import Count, Q
from datetime import datetime, timedelta
from .models import Transaction, RejectedSMS
from sms_parser.parser import parse_sms
from datetime import datetime
from django.db import IntegrityError
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes



# ✅ Providers API (used by Flutter to get allowed senders)
class ProviderListAPIView(generics.ListAPIView):
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer


from .models import Provider
def handle_sms_submission(sms_text, sender=None, user=None):
    parsed = parse_sms(sms_text, sender)

    # ✅ Provider must still exist
    provider_name = parsed.get("network_provider", "").upper()
    if not Provider.objects.filter(name__iexact=provider_name).exists():
        RejectedSMS.objects.create(
            sender=sender or "UNKNOWN",
            message=sms_text,
            reason=f"Unknown provider: {provider_name}"
        )
        return {"saved": False, "rejected": True, "parsed": parsed, "error": "Unknown provider"}

    # ✅ No rejection for missing reference_id or amount (temporarily)
    is_incomplete = False
    if not parsed.get("reference_id") or parsed.get("amount") is None:
        is_incomplete = True

    reference_id = parsed.get("reference_id") or f"UNKNOWN-{datetime.now().timestamp()}"
    amount = parsed.get("amount") or 0.0

    try:
        transaction, created = Transaction.objects.get_or_create(
            reference_id=reference_id,
            defaults={
                "network_provider": provider_name,
                "type": parsed.get("type") or "unknown",
                "amount": amount,
                "customer_phone": parsed.get("customer_phone"),
                "customer_name": parsed.get("customer_name"),
                "balance": parsed.get("balance"),
                "transaction_fee": parsed.get("transaction_fee"),
                "date_transaction": parsed.get("date_transaction") or datetime.now(),
                "raw_sms": sms_text,
                "sender": sender,
                "user": user,
                "is_incomplete": is_incomplete  # ✅ Save the flag
            }
        )


        if not created:
            return {"saved": False, "rejected": False, "parsed": parsed, "error": "Duplicate reference_id"}

        return {"saved": True, "rejected": False, "parsed": parsed}

    except IntegrityError as e:
        return {"saved": False, "rejected": False, "parsed": parsed, "error": str(e)}



# ✅ Parse API - used by Flutter
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def parse_and_store_sms(request):
    sms = request.data.get("sms")
    sender = request.data.get("sender")

    if not sms:
        return Response({"error": "No SMS provided."}, status=status.HTTP_400_BAD_REQUEST)

    result = handle_sms_submission(sms, sender, request.user)

    if result["saved"]:
        return Response({"status": "saved", "data": result["parsed"]}, status=status.HTTP_201_CREATED)
    elif result["rejected"]:
        return Response({"status": "rejected", "data": result["parsed"]}, status=status.HTTP_403_FORBIDDEN)
    else:
        return Response({"status": "error", "message": result["error"]}, status=status.HTTP_400_BAD_REQUEST)


# ✅ Transaction List API for Flutter App
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_transactions(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-date_transaction')
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


# ✅ Filtered provider transactions API

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def provider_transactions_api(request, provider):
    query = request.GET.get("q", "")
    filtered = Transaction.objects.filter(user=request.user, network_provider__iexact=provider)

    if query:
        filtered = filtered.filter(
            Q(reference_id__icontains=query) |
            Q(customer_phone__icontains=query) |
            Q(type__icontains=query)
        )

    serializer = TransactionSerializer(filtered.order_by('-date_transaction'), many=True)
    return Response(serializer.data)


# ✅ Dashboard Summary API
from rest_framework.decorators import api_view
from rest_framework.response import Response
from transactions.models import Transaction
from django.db.models import Sum, Count
from datetime import datetime, timedelta
from django.utils.timezone import localtime


# APIS
from django.utils.timezone import now, timedelta
from django.db.models import Count
from rest_framework.decorators import api_view
from rest_framework.response import Response
from transactions.models import Transaction
from rest_framework.response import Response
from transactions.models import Transaction
from django.db.models import Sum, Count
from datetime import datetime, timedelta
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary_view(request):
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    totals = {
        "today": Transaction.objects.filter(user=request.user, date_transaction__date=today).count(),
        "week": Transaction.objects.filter(user=request.user, date_transaction__date__gte=week_start).count(),
        "month": Transaction.objects.filter(user=request.user, date_transaction__date__gte=month_start).count(),
        "year": Transaction.objects.filter(user=request.user, date_transaction__date__gte=year_start).count(),
    }

    providers = (
        Transaction.objects.filter(user=request.user)
        .values("network_provider")
        .annotate(total=Count("id"))
        .order_by("network_provider")
    )

    income = Transaction.objects.filter(
        user=request.user,
        type__in=['received', 'deposit'],
        date_transaction__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0

    expenses = Transaction.objects.filter(
        user=request.user,
        type__in=['payment', 'withdrawal', 'airtime'],
        date_transaction__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0

    latest_txn = Transaction.objects.filter(user=request.user).order_by('-date_transaction').first()
    balance = latest_txn.balance if latest_txn else 0

    recent_transactions = (
        Transaction.objects
        .filter(user=request.user)
        .order_by('-date_transaction')[:10]
        .values('reference_id', 'type', 'amount', 'customer_name', 'customer_phone', 'date_transaction', 'network_provider')
    )

    recent_list = []
    for txn in recent_transactions:
        local_dt = localtime(txn['date_transaction'])
        txn['formatted_date'] = local_dt.strftime("%d %b, %I:%M %p")
        recent_list.append(txn)

    return Response({
        "totals": totals,
        "providers": list(providers),
        "total_all": Transaction.objects.filter(user=request.user).count(),
        "financial_summary": {
            "current_balance": balance,
            "total_income": income,
            "total_expenses": expenses,
            "net_change": income - expenses
        },
        "recent_transactions": recent_list
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def filters_view(request):
    providers = Transaction.objects.filter(user=request.user).values_list('network_provider', flat=True).distinct()
    types = Transaction.objects.filter(user=request.user).values_list('type', flat=True).distinct()

    return Response({
        "providers": list(providers),
        "types": list(types)
    })



from transactions.models import Transaction
from transactions.serializers import TransactionSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_transactions_view(request):
    provider = request.GET.get('provider', None)
    txn_type = request.GET.get('type', None)
    start_date = request.GET.get('start_date', None)
    end_date = request.GET.get('end_date', None)

    transactions = Transaction.objects.filter(user=request.user).order_by('-date_transaction')

    if provider:
        transactions = transactions.filter(network_provider__iexact=provider)

    if txn_type:
        transactions = transactions.filter(type__iexact=txn_type)

    if start_date:
        transactions = transactions.filter(date_transaction__date__gte=start_date)

    if end_date:
        transactions = transactions.filter(date_transaction__date__lte=end_date)

    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def providers_with_transactions(request):
    trusted_providers = list(Provider.objects.values_list('name', flat=True))

    providers = (
        Transaction.objects
        .filter(user=request.user, network_provider__in=trusted_providers)
        .values("network_provider")
        .annotate(total=Count("id"))
        .filter(total__gt=0)
        .order_by("network_provider")
    )

    return Response(list(providers))



# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def providers_view(request):
#     providers = Provider.objects.all()
#     response_data = []

#     for provider in providers:
#         total = Transaction.objects.filter(user=request.user, network_provider__iexact=provider.name).count()
#         response_data.append({
#             "network_provider": provider.name,
#             "total": total
#         })

#     return Response(response_data)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from transactions.models import Provider, Transaction

@api_view(['GET'])
# @permission_classes([IsAuthenticated])  # 🔒 Commented out for now
def providers_view(request):
    providers = Provider.objects.all()
    response_data = []

    for provider in providers:
        total = Transaction.objects.filter(network_provider__iexact=provider.name).count()
        response_data.append({
            "network_provider": provider.name,
            "total": total
        })

    return Response(response_data)




from rest_framework.decorators import api_view
from rest_framework.response import Response
from transactions.models import Transaction
from django.db.models import Sum
from django.utils.timezone import now
import calendar

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def charts_summary_view(request):
    # Income vs Expense monthly summary (last 6 months)
    income_data = []
    expense_data = []
    labels = []

    today = now().date()

    for i in range(5, -1, -1):  # last 6 months
        month_date = today.replace(day=1) - timedelta(days=i*30)
        month_start = month_date.replace(day=1)
        month_end = month_date.replace(day=calendar.monthrange(month_date.year, month_date.month)[1])

        income = Transaction.objects.filter(
            user=request.user,
            type__in=['received', 'deposit'],
            date_transaction__date__range=(month_start, month_end)
        ).aggregate(total=Sum('amount'))['total'] or 0

        expense = Transaction.objects.filter(
            user=request.user,
            type__in=['payment', 'withdrawal', 'airtime'],
            date_transaction__date__range=(month_start, month_end)
        ).aggregate(total=Sum('amount'))['total'] or 0

        income_data.append(income)
        expense_data.append(expense)
        labels.append(month_start.strftime('%b'))

    # Provider Pie Chart data
    providers = (
        Transaction.objects.filter(user=request.user)
        .values('network_provider')
        .annotate(total=Sum('amount'))
        .order_by('network_provider')
    )

    return Response({
        "income_data": income_data,
        "expense_data": expense_data,
        "labels": labels,
        "providers": list(providers),
    })



from django.http import HttpResponse
from django.db.models import Sum
from django.utils.timezone import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from urllib.parse import unquote
from transactions.models import Transaction

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_pdf_report(request):
    provider = request.GET.get("provider", "").strip()
    txn_type = request.GET.get("type", "").strip()
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    # ✅ Filter by current user
    transactions = Transaction.objects.filter(user=request.user)

    if provider:
        provider = unquote(provider).upper()
        transactions = transactions.filter(network_provider__iexact=provider)

    if txn_type:
        txn_type = unquote(txn_type).lower()
        transactions = transactions.filter(type__iexact=txn_type)

    if start_date:
        transactions = transactions.filter(date_transaction__date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date_transaction__date__lte=end_date)

    total_count = transactions.count()
    total_amount = sum([t.amount or 0 for t in transactions])

    type_summary = transactions.values('type').annotate(total=Sum('amount'))
    provider_summary = transactions.values('network_provider').annotate(total=Sum('amount'))

    income_total = sum([t.amount for t in transactions if t.type in ['received', 'deposit']])
    expense_total = sum([t.amount for t in transactions if t.type in ['payment', 'withdrawal', 'airtime']])
    net_change = (income_total or 0) - (expense_total or 0)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=transactions_report.pdf"

    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=80, bottomMargin=60)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>TRANSACTION SMS REPORT</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Provider:</b> {provider or 'ALL'}", styles['Normal']))
    elements.append(Paragraph(f"<b>Type:</b> {txn_type or 'ALL'}", styles['Normal']))
    elements.append(Paragraph(f"<b>Period:</b> {start_date or '-'} to {end_date or '-'}", styles['Normal']))
    elements.append(Spacer(1, 12))

    summary_data = [
        ["Total Transactions", total_count],
        ["Total Amount", f"TZS {total_amount:,.2f}"],
        ["Total Income", f"TZS {income_total:,.2f}"],
        ["Total Expenses", f"TZS {expense_total:,.2f}"],
        ["Net Change", f"TZS {net_change:,.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[150, 200])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("<b>Type Breakdown:</b>", styles['Heading3']))
    type_data = [["Type", "Total Amount"]]
    for item in type_summary:
        type_data.append([item['type'].capitalize(), f"TZS {item['total']:,.2f}"])

    type_table = Table(type_data, colWidths=[200, 150])
    type_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(type_table)
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("<b>Provider Breakdown:</b>", styles['Heading3']))
    provider_data = [["Provider", "Total Amount"]]
    for item in provider_summary:
        provider_data.append([item['network_provider'], f"TZS {item['total']:,.2f}"])

    provider_table = Table(provider_data, colWidths=[200, 150])
    provider_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(provider_table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>Full Transaction List:</b>", styles['Heading3']))
    headers = ["No", "Date", "Reference ID", "Type", "Amount", "Phone", "Provider"]
    table_data = [headers]

    for idx, t in enumerate(transactions):
        row = [
            str(idx + 1),
            t.date_transaction.strftime('%d-%m-%y %H:%M'),
            t.reference_id or "-",
            t.type.capitalize(),
            f"{t.amount:,.2f}" if t.amount else "-",
            t.customer_phone or "-",
            t.network_provider or "-"
        ]
        table_data.append(row)

    page_size = 40
    for i in range(0, len(table_data), page_size):
        chunk = table_data[i:i + page_size]
        table = Table(chunk, colWidths=[30, 90, 80, 60, 80, 100, 70])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
        if i + page_size < len(table_data):
            elements.append(PageBreak())

    def add_footer(canvas, doc):
        canvas.saveState()
        footer_text = f"Generated on {datetime.now().strftime('%d-%m-%Y %H:%M')}"
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(570, 20, footer_text)
        canvas.restoreState()

    doc.build(elements, onLaterPages=add_footer, onFirstPage=add_footer)

    return response

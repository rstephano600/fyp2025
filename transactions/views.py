
from .models import Transaction, RejectedSMS
from sms_parser.parser import parse_sms
from .models import Transaction
from django.shortcuts import render
from .forms import SMSForm
from .models import Transaction, RejectedSMS
from datetime import datetime
from django.db import IntegrityError
from transactions.models import Transaction
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from .models import Transaction
from datetime import datetime


def index(request):
        return render(request, 'transactions/index.html', {})

def sms_upload_form(request):
    saved = False
    rejected = False
    parsed = None
    error = None

    if request.method == 'POST':
        form = SMSForm(request.POST)
        if form.is_valid():
            sms = form.cleaned_data['sms']
            parsed = parse_sms(sms)

            # Only save if SMS is legit
            if parsed['type'] != 'unknown' and parsed['network_provider'] != 'UNKNOWN':
                try:
                    Transaction.objects.create(
                        reference_id = parsed.get("reference_id"),
                        network_provider = parsed.get("network_provider"),
                        type = parsed.get("type"),
                        amount = parsed.get("amount"),
                        customer_phone = parsed.get("customer_phone") or "UNKNOWN",
                        customer_name = parsed.get("customer_name"),
                        balance = parsed.get("balance"),
                        transaction_fee = parsed.get("transaction_fee"),
                        date_transaction = parsed.get("date_transaction") or datetime.now(),
                        raw_sms = sms
                    )
                    saved = True
                except IntegrityError as e:
                    if "UNIQUE constraint failed" in str(e):
                        error = "⚠️ This SMS was already processed (duplicate reference ID)."
                        amount = parsed.get("amount")
                    if not amount:
                        error = "❌ Amount not found. SMS was not saved."
                    else:
                        error = f"❌ Failed to save SMS: {str(e)}"
            else:
                RejectedSMS.objects.create(
                    sender = parsed.get("customer_phone") or "UNKNOWN",
                    message = sms,
                    reason = "Rejected in web form: unrecognized type/provider"
                )
                rejected = True
    else:
        form = SMSForm()

    return render(request, 'transactions/sms_form.html', {
        'form': form,
        'saved': saved,
        'rejected': rejected,
        'error': error,
    })


from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

@api_view(['POST'])
def register_user(request):
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email")

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists."}, status=400)

    user = User.objects.create_user(username=username, password=password, email=email)
    refresh = RefreshToken.for_user(user)

    return Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'username': user.username
    }, status=201)


from django.http import HttpResponse
from django.db.models import Sum
from django.utils.timezone import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from urllib.parse import unquote
from transactions.models import Transaction

def generate_pdf_report(request):
    provider = request.GET.get("provider", "").strip()
    txn_type = request.GET.get("type", "").strip()
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    transactions = Transaction.objects.all()

    # ✅ Safely filter provider
    if provider:
        provider = unquote(provider).upper()
        transactions = transactions.filter(network_provider__iexact=provider)

    # ✅ Safely filter type
    if txn_type:
        txn_type = unquote(txn_type).lower()
        transactions = transactions.filter(type__iexact=txn_type)

    # ✅ Safely filter dates
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

    # ✅ Report Header
    elements.append(Paragraph("<b>TRANSACTION SMS REPORT</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Provider:</b> {provider or 'ALL'}", styles['Normal']))
    elements.append(Paragraph(f"<b>Type:</b> {txn_type or 'ALL'}", styles['Normal']))
    elements.append(Paragraph(f"<b>Period:</b> {start_date or '-'} to {end_date or '-'}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # ✅ Financial Summary
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

    # ✅ Type Breakdown
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

    # ✅ Provider Breakdown
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

    # ✅ Full Transaction List
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

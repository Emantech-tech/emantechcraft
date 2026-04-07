from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from datetime import datetime, timedelta
from .forms import SignUpForm, LoginForm
from .models import Party, Transaction, UserProfile
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db import transaction as db_transaction
from django.db import models

# ✅ Try to import weasyprint for Urdu PDF
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


# ==============================
# 🔹 HELPER: Check Subscription Access (NO TRIAL)
# ==============================
def check_subscription_access(user):
    """Check if user has active subscription - NO FREE TRIAL"""
    if not user.is_authenticated:
        return True

    try:
        profile = user.profile
        return profile.has_active_access()
    except UserProfile.DoesNotExist:
        # Create profile for existing user (NO trial)
        UserProfile.objects.create(user=user)
        return False

def intro_slip(request):
    """
    Intro slip page - only for non-authenticated users, and only once.
    Once viewed or after login, it will never show again.
    """
    # If user is authenticated, redirect to landing page directly
    if request.user.is_authenticated:
        return redirect('landing')

    # Check if user has already seen the intro (via session or cookie)
    # Using session is more secure and user-specific
    if request.session.get('intro_seen', False):
        return redirect('landing')

    # Also check cookie as fallback (for users who clear sessions)
    if request.COOKIES.get('intro_seen') == 'true':
        return redirect('landing')

    response = render(request, 'intro_slip.html')

    # Set session flag that intro has been shown
    request.session['intro_seen'] = True

    # Set a cookie that expires after 1 year (365 days)
    # This ensures even if session expires, intro won't show again
    response.set_cookie(
        'intro_seen',
        'true',
        max_age=365 * 24 * 60 * 60,  # 1 year
        httponly=False,  # Allow JavaScript to read if needed
        samesite='Lax',
        path='/'
    )

    return response
# ==============================
# 🔹 SUBSCRIPTION VIEWS
# ==============================
@login_required
def subscribe_view(request):
    """Show subscription page with bank details"""
    profile = request.user.profile

    # Meezan Bank account details
    bank_details = {
        'bank_name': 'Meezan Bank Limited',
        'account_title': 'Eman Farhat',
        'account_number': '9855 01114457982',
        'iban': 'PK15MEZN 0098 5501 1445 7982',
        'branch_code': '9855',
        'amount': '3000',
        'whatsapp': '03079402909'
    }

    return render(request, 'subscribe.html', {
        'profile': profile,
        'bank_details': bank_details
    })


@login_required
def activate_subscription_manual(request, user_id):
    """Admin manually activate subscription (called from admin or custom view)"""
    if not request.user.is_staff:
        messages.error(request, 'You are not authorized to perform this action.')
        return redirect('dashboard')

    profile = get_object_or_404(UserProfile, user__id=user_id)
    profile.activate_subscription(months=1)
    messages.success(request, f'Subscription activated for {profile.user.username}')
    return redirect('admin:ca_userprofile_changelist')


# ==============================
# 🔹 DASHBOARD (with subscription check)
# ==============================
@login_required
def dashboard(request):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue using Munshi.')
        return redirect('subscribe')

    parties = Party.objects.filter(user=request.user)

    total_debit = parties.aggregate(total=Sum('total_debit'))['total'] or Decimal('0')
    total_credit = parties.aggregate(total=Sum('total_credit'))['total'] or Decimal('0')

    return render(request, 'dashboard.html', {
        'parties': parties,
        'total_debit': total_debit,
        'total_credit': total_credit,
    })


# ==============================
# 🔹 ADD PARTY
# ==============================
@login_required
def add_party(request):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        cnic = request.POST.get('cnic')
        address = request.POST.get('address')
        shop_name = request.POST.get('shop_name', '')
        opening_amount = request.POST.get('opening_balance', '0')
        balance_type = request.POST.get('balance_type', 'debit')

        party = Party(
            user=request.user,
            name=name,
            phone=phone,
            cnic=cnic,
            address=address,
            shop_name=shop_name,
        )

        try:
            party.full_clean()
            party.save()

            try:
                opening_amount = Decimal(opening_amount)
                if opening_amount > 0:
                    if balance_type == 'debit':
                        Transaction.objects.create(
                            party=party,
                            debit=opening_amount,
                            credit=Decimal('0'),
                            product_name="Opening Balance",
                            reference="Opening Balance",
                            date=timezone.now().date(),
                            note="ابتدائی بیلنس - نام"
                        )
                    else:
                        Transaction.objects.create(
                            party=party,
                            debit=Decimal('0'),
                            credit=opening_amount,
                            product_name="Opening Balance",
                            reference="Opening Balance",
                            date=timezone.now().date(),
                            note="ابتدائی بیلنس - جمع"
                        )
            except Exception as e:
                print(f"Opening balance error: {e}")
                pass

            messages.success(request, f'Party "{name}" successfully add ho gaya!')
            return redirect('dashboard')

        except ValidationError as e:
            messages.error(request, e.messages)
            return render(request, 'add_party.html', {'error': e.messages})

    return render(request, 'add_party.html')


# ==============================
# 🔹 EDIT PARTY
# ==============================
@login_required
def edit_party(request, id):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    party = get_object_or_404(Party, id=id, user=request.user)

    if request.method == "POST":
        party.name = request.POST.get('name')
        party.phone = request.POST.get('phone')
        party.cnic = request.POST.get('cnic')
        party.address = request.POST.get('address')
        party.shop_name = request.POST.get('shop_name', '')
        party.save()
        messages.success(request, 'Party updated successfully!')
        return redirect('dashboard')

    return render(request, 'edit_party.html', {'party': party})


# ==============================
# 🔹 PARTY DETAIL (Ledger View)
# ==============================
@login_required
def party_detail(request, id):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    party = get_object_or_404(Party, id=id, user=request.user)
    transactions = Transaction.objects.filter(party=party).order_by('date', 'id')

    room_no = request.GET.get('room_no')
    if room_no:
        transactions = transactions.filter(room_no=room_no)

    room_numbers = Transaction.objects.filter(party=party).values_list('room_no', flat=True).distinct().exclude(room_no__isnull=True).exclude(room_no='')

    return render(request, 'party_detail.html', {
        'party': party,
        'transactions': transactions,
        'room_no': room_no,
        'room_numbers': room_numbers,
    })


# ==============================
# 🔹 DELETE PARTY
# ==============================
@login_required
def delete_party(request, id):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    party = get_object_or_404(Party, id=id, user=request.user)

    if request.method == "POST":
        party.delete()
        messages.success(request, 'Party deleted successfully!')
        return redirect('dashboard')

    return render(request, 'confirm_delete.html', {'party': party})


# ==============================
# 🔹 AUTH VIEWS (WITH OTP VERIFICATION)
# ==============================

import random
import time
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from .forms import SignUpForm, LoginForm
from .models import UserProfile

# ==============================
# 🔹 OTP FUNCTIONS
# ==============================

def generate_otp():
    """Generate 6-digit OTP"""
    return str(random.randint(100000, 999999))

def send_otp_email(email, otp, lang='en'):
    """Send OTP to email"""
    if lang == 'ur':
        subject = 'منشی - اکاؤنٹ کی تصدیق'
        message = f'''
        <html>
        <body style="font-family: 'Noto Nastaliq Urdu', Arial, sans-serif; direction: rtl;">
            <div style="max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e8e4dd; border-radius: 12px;">
                <h2 style="color: #c9a84c;">منشی تصدیقی کوڈ</h2>
                <p>آپ کا OTP ہے:</p>
                <div style="font-size: 32px; font-weight: bold; color: #b85c38; padding: 15px; background: #faf7f2; text-align: center; border-radius: 10px; letter-spacing: 5px;">
                    {otp}
                </div>
                <p>یہ کوڈ <strong>5 منٹ</strong> کے لیے درست ہے۔</p>
                <p style="color: #7a7067; font-size: 12px;">یہ کوڈ کسی کے ساتھ شیئر نہ کریں۔</p>
                <hr style="border: none; border-top: 1px solid #e8e4dd;">
                <p style="color: #7a7067; font-size: 12px;">شکریہ،<br>Eman TechCraft</p>
            </div>
        </body>
        </html>
        '''
    else:
        subject = 'Munshi - Account Verification'
        message = f'''
        <html>
        <body style="font-family: Arial, sans-serif; direction: ltr;">
            <div style="max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e8e4dd; border-radius: 12px;">
                <h2 style="color: #c9a84c;">Munshi Verification Code</h2>
                <p>Your OTP for account verification is:</p>
                <div style="font-size: 32px; font-weight: bold; color: #b85c38; padding: 15px; background: #faf7f2; text-align: center; border-radius: 10px; letter-spacing: 5px;">
                    {otp}
                </div>
                <p>This code is valid for <strong>5 minutes</strong>.</p>
                <p style="color: #7a7067; font-size: 12px;">Do not share this code with anyone.</p>
                <hr style="border: none; border-top: 1px solid #e8e4dd;">
                <p style="color: #7a7067; font-size: 12px;">Regards,<br>Eman TechCraft</p>
            </div>
        </body>
        </html>
        '''

    try:
        send_mail(
            subject,
            '',  # Plain text version empty
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
            html_message=message
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# ==============================
# 🔹 SEND OTP VIEW (AJAX)
# ==============================

def send_otp_view(request):
    """Send OTP to email via AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            lang = data.get('lang', 'en')

            if not email:
                return JsonResponse({'success': False, 'error': 'Email is required'})

            # Check if email already exists
            from django.contrib.auth.models import User
            if User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'Email already registered. Please login.'})

            otp = generate_otp()

            # Store in session
            request.session['otp'] = otp
            request.session['otp_email'] = email
            request.session['otp_time'] = time.time()

            # Send email
            if send_otp_email(email, otp, lang):
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Failed to send email. Please try again.'})

        except Exception as e:
            print(f"Error in send_otp_view: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ==============================
# 🔹 VERIFY OTP VIEW (AJAX)
# ==============================

def verify_otp_view(request):
    """Verify OTP via AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_otp = data.get('otp')
            email = data.get('email')

            saved_otp = request.session.get('otp')
            saved_email = request.session.get('otp_email')
            otp_time = request.session.get('otp_time', 0)

            # Check expiry (5 minutes = 300 seconds)
            if time.time() - otp_time > 300:
                return JsonResponse({'success': False, 'error': 'OTP has expired. Please request a new one.'})

            if saved_otp and str(user_otp) == str(saved_otp) and saved_email == email:
                request.session['email_verified'] = True
                return JsonResponse({'success': True})

            return JsonResponse({'success': False, 'error': 'Invalid OTP. Please try again.'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ==============================
# 🔹 SIGNUP VIEW (WITH OTP)
# ==============================

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)

        # Check if email is verified
        if not request.session.get('email_verified', False):
            messages.error(request, 'Please verify your email first.')
            return render(request, 'signup.html', {'form': form})

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password1'])
            user.save()

            # Create UserProfile (NO trial - not subscribed)
            UserProfile.objects.create(user=user)

            # Clear OTP session
            request.session.pop('email_verified', None)
            request.session.pop('otp', None)
            request.session.pop('otp_email', None)
            request.session.pop('otp_time', None)

            messages.success(request, '✅ Account created successfully! Please subscribe to continue.')
            return redirect('subscribe')
        else:
            return render(request, 'signup.html', {'form': form})
    else:
        form = SignUpForm()

    return render(request, 'signup.html', {'form': form})


# ==============================
# 🔹 LOGIN VIEW (NO CAPTCHA)
# ==============================

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            # Check subscription status
            try:
                profile = user.profile
                print(f"User: {user.username}")
                print(f"is_subscribed: {profile.is_subscribed}")
                print(f"subscription_end_date: {profile.subscription_end_date}")
                print(f"has_active_access: {profile.has_active_access()}")
                print(f"Current time: {timezone.now()}")
            except:
                print("No profile found")

            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'form': form})
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})



@login_required
def check_subscription_status(request):
    """Check if user has active access"""
    return JsonResponse({
        'has_active_access': check_subscription_access(request.user)
    })
def logout_view(request):
    logout(request)
    messages.success(request, "آپ لاگ آؤٹ ہو چکے ہیں!")
    return redirect('login')


def landing(request):
    return render(request, 'landing.html')


# ==============================
# 🔹 ADD TRANSACTION
# ==============================
@login_required
def add_transaction(request, party_id):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    party = get_object_or_404(Party, id=party_id, user=request.user)

    if request.method == 'POST':
        date_str = request.POST.get('date')
        room_no = request.POST.get('room_no', '')
        product_name = request.POST.get('product_name', '')
        qty = request.POST.get('qty', '0')
        rate = request.POST.get('rate', '0')
        commission = request.POST.get('commission', '0')
        bharti = request.POST.get('bharti', '0')
        ant = request.POST.get('ant', '0')
        rokad = request.POST.get('rokad', '0')
        transaction_type = request.POST.get('transaction_type', '')
        reference = request.POST.get('reference', '')
        note = request.POST.get('note', '')

        try:
            qty = Decimal(qty) if qty else Decimal('0')
            rate = Decimal(rate) if rate else Decimal('0')
            commission_amt = Decimal(commission) if commission else Decimal('0')
            bharti_amt = Decimal(bharti) if bharti else Decimal('0')
            ant_amt = Decimal(ant) if ant else Decimal('0')
            rokad_amt = Decimal(rokad) if rokad else Decimal('0')

            if not transaction_type:
                messages.error(request, 'براہ کرم ٹرانزیکشن کی قسم منتخب کریں!')
                return render(request, 'add_transaction.html', {'party': party})

            if ant_amt <= 0:
                messages.error(request, 'براہ کرم انت (خالص رقم) صفر سے زیادہ درج کریں!')
                return render(request, 'add_transaction.html', {'party': party})

            if date_str:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date_obj = timezone.now().date()

            debit_amt = Decimal('0')
            credit_amt = Decimal('0')

            if transaction_type == 'debit':
                debit_amt = ant_amt
            elif transaction_type == 'credit':
                credit_amt = ant_amt
            else:
                messages.error(request, 'براہ کرم درست ٹرانزیکشن کی قسم منتخب کریں!')
                return render(request, 'add_transaction.html', {'party': party})

            transaction = Transaction(
                party=party,
                date=date_obj,
                room_no=room_no,
                product_name=product_name,
                qty=qty,
                rate=rate,
                commission=commission_amt,
                bharti=bharti_amt,
                ant=ant_amt,
                rokad=rokad_amt,
                debit=debit_amt,
                credit=credit_amt,
                reference=reference,
                note=note,
            )
            transaction.save()

            messages.success(request, 'ٹرانزیکشن کامیابی سے شامل ہو گئی!')
            return redirect('party_detail', id=party.id)

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return render(request, 'add_transaction.html', {'party': party})

    return render(request, 'add_transaction.html', {'party': party})


# ==============================
# 🔹 EDIT TRANSACTION
# ==============================
@login_required
def edit_transaction(request, pk):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    transaction = get_object_or_404(Transaction, id=pk, party__user=request.user)
    party = transaction.party

    if request.method == 'POST':
        old_debit = transaction.debit
        old_credit = transaction.credit

        transaction.room_no = request.POST.get('room_no', transaction.room_no)
        transaction.product_name = request.POST.get('product_name', transaction.product_name)
        transaction.reference = request.POST.get('reference', transaction.reference)
        transaction.note = request.POST.get('note', transaction.note)

        try:
            transaction.date = datetime.strptime(request.POST.get('date'), '%Y-%m-%d').date()
            transaction.qty = Decimal(request.POST.get('qty', transaction.qty))
            transaction.rate = Decimal(request.POST.get('rate', transaction.rate))
            transaction.commission = Decimal(request.POST.get('commission', transaction.commission or 0))
            transaction.bharti = Decimal(request.POST.get('bharti', transaction.bharti or 0))
            transaction.ant = Decimal(request.POST.get('ant', transaction.ant or 0))
            transaction.rokad = Decimal(request.POST.get('rokad', transaction.rokad or 0))

            new_debit = Decimal(request.POST.get('debit', transaction.debit))
            new_credit = Decimal(request.POST.get('credit', transaction.credit))

            if new_debit > 0 and new_credit > 0:
                messages.error(request, 'ایک ٹرانزیکشن میں صرف نام یا جمع میں سے ایک ہو سکتا ہے!')
                return render(request, 'edit_transaction.html', {'transaction': transaction, 'party': party})

            transaction.debit = new_debit
            transaction.credit = new_credit

        except Exception as e:
            messages.error(request, f'Invalid data: {e}')
            return render(request, 'edit_transaction.html', {'transaction': transaction, 'party': party})

        party.total_debit += (transaction.debit - old_debit)
        party.total_credit += (transaction.credit - old_credit)
        party.save()

        transaction.save()
        recalculate_balances(party, transaction.date, transaction.id)

        messages.success(request, 'ٹرانزیکشن اپ ڈیٹ ہو گئی!')
        return redirect('party_detail', id=party.id)

    return render(request, 'edit_transaction.html', {'transaction': transaction, 'party': party})


# ==============================
# 🔹 DELETE TRANSACTION
# ==============================
def delete_transaction(request, transaction_id):
    trans = get_object_or_404(Transaction, id=transaction_id)
    party = trans.party

    if request.method == 'POST':
        with db_transaction.atomic():
            debit_amount = trans.debit
            credit_amount = trans.credit

            if debit_amount > 0:
                party.total_debit -= debit_amount
            if credit_amount > 0:
                party.total_credit -= credit_amount
            party.save()

            trans.delete()

            all_transactions = Transaction.objects.filter(party=party).order_by('date', 'id')

            running_balance = Decimal('0')
            for t in all_transactions:
                running_balance = running_balance + (t.credit - t.debit)
                t.balance = running_balance
                t.save()

        messages.success(request, f"Transaction deleted successfully!")
        return redirect('party_detail', id=party.id)

    context = {
        'transaction': trans,
        'party': party,
    }
    return render(request, 'delete_transaction.html', context)


# ==============================
# 🔹 HELPER FUNCTION: Recalculate Balances
# ==============================
def recalculate_balances(party, from_date=None, exclude_id=None, delete_id=None):
    transactions = Transaction.objects.filter(party=party).order_by('date', 'id')

    if from_date:
        transactions = transactions.filter(date__gte=from_date)

    if exclude_id:
        transactions = transactions.exclude(id=exclude_id)

    running_balance = Decimal('0')

    for t in transactions:
        if t == transactions.first():
            prev_transactions = Transaction.objects.filter(
                party=party,
                date__lt=t.date
            ).order_by('-date', '-id')

            if prev_transactions.exists():
                running_balance = prev_transactions.first().balance
            else:
                same_date_older = Transaction.objects.filter(
                    party=party,
                    date=t.date,
                    id__lt=t.id
                ).order_by('-id')
                if same_date_older.exists():
                    running_balance = same_date_older.first().balance
                else:
                    running_balance = Decimal('0')

        t.balance = running_balance + (t.credit - t.debit)
        running_balance = t.balance
        t.save(update_fields=['balance'])


# ==============================
# 🔹 PDF GENERATION
# ==============================
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm

@login_required
def generate_pdf_english(request, party_id):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    party = get_object_or_404(Party, id=party_id, user=request.user)
    transactions = Transaction.objects.filter(party=party).order_by('date', 'id')

    room_no = request.GET.get('room_no')
    if room_no:
        transactions = transactions.filter(room_no=room_no)

    shop_name = party.shop_name if party.shop_name else ''

    response = HttpResponse(content_type='application/pdf')
    filename = f"{party.name}_account.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=10*mm,
        rightMargin=10*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Normal'],
        fontSize=11,
        alignment=1,
        spaceAfter=6,
        fontName='Helvetica-Bold',
    )

    shop_style = ParagraphStyle(
        'ShopStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1,
        spaceAfter=4,
        fontName='Helvetica',
        textColor=colors.HexColor('#b85c38'),
    )

    elements.append(Paragraph("MERAN CROP SCIENCES", title_style))

    if shop_name:
        elements.append(Paragraph(f"Shop: {shop_name}", shop_style))

    elements.append(Paragraph(f"Party: {party.name}", title_style))
    if room_no:
        elements.append(Paragraph(f"Room No: {room_no}", title_style))
    elements.append(Spacer(1, 0.1 * inch))

    summary_data = [
        ['Total Credit (Jama)', f'Rs. {party.total_credit:,.2f}'],
        ['Total Debit (Naam)', f'Rs. {party.total_debit:,.2f}'],
        ['Net Balance', f'Rs. {abs(party.balance):,.2f}'],
    ]
    summary_table = Table(summary_data, colWidths=[80, 80])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8e8e8')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.15 * inch))

    col_widths = [52, 35, 100, 38, 45, 45, 50, 45, 55, 55, 62]
    data = [
        ['Date', 'Qty', 'Product', 'Rate', 'Rokad', 'Ant\n(Net Amount)', 'Bharti\n(KG)', 'Commission',  'Naam\n(Debit)', 'Jama\n(Credit)', 'Balance']
    ]

    row_debit_cols = []
    row_credit_cols = []
    row_balance_colors = []

    total_rokad = Decimal('0')
    total_commission = Decimal('0')
    total_ant = Decimal('0')

    for i, t in enumerate(transactions):
        row_index = i + 1

        date_str = t.date.strftime('%d-%m-%Y') if t.date else ''
        product_name = t.product_name or ''
        if len(product_name) > 20:
            product_name = product_name[:17] + '...'

        qty_str = f'{t.qty:,.2f}' if t.qty else '0'
        rate_str = f'{t.rate:,.2f}' if t.rate else '0'
        commission_str = f'{t.commission:,.2f}' if t.commission else '0'
        bharti_str = f'{t.bharti:,.3f}' if t.bharti else '0'
        ant_str = f'{t.ant:,.2f}' if t.ant else '0'
        rokad_str = f'{t.rokad:,.2f}' if t.rokad and t.rokad > 0 else '0'
        debit_str = f'{t.debit:,.2f}' if t.debit > 0 else ''
        credit_str = f'{t.credit:,.2f}' if t.credit > 0 else ''

        if t.rokad:
            total_rokad += t.rokad
        if t.commission:
            total_commission += t.commission
        if t.ant:
            total_ant += t.ant

        if t.balance > 0:
            balance_str = f'({t.balance:,.2f})'
        elif t.balance < 0:
            balance_str = f'{abs(t.balance):,.2f}'
        else:
            balance_str = '0.00'

        data.append([
            date_str, qty_str, product_name, rate_str,
            commission_str, bharti_str, ant_str, rokad_str, debit_str, credit_str, balance_str
        ])

        if t.debit > 0:
            row_debit_cols.append(row_index)
        if t.credit > 0:
            row_credit_cols.append(row_index)

        if t.balance < 0:
            row_balance_colors.append((row_index, colors.red))
        elif t.balance > 0:
            row_balance_colors.append((row_index, colors.HexColor('#1a56db')))
        else:
            row_balance_colors.append((row_index, colors.black))

    total_row_index = len(transactions) + 1
    data.append([
        'TOTAL', '', '', '',
        f'{total_commission:,.2f}', '', f'{total_ant:,.2f}', f'{total_rokad:,.2f}',
        f'{party.total_debit:,.2f}', f'{party.total_credit:,.2f}', ''
    ])

    table = Table(data, colWidths=col_widths, repeatRows=1)

    base_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
        ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
        ('ALIGN', (7, 1), (7, -1), 'RIGHT'),
        ('ALIGN', (8, 1), (8, -1), 'RIGHT'),
        ('ALIGN', (9, 1), (9, -1), 'RIGHT'),
        ('ALIGN', (10, 1), (10, -1), 'RIGHT'),
        ('FONTSIZE', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f9f9f9')]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]

    base_style.append(('BACKGROUND', (0, total_row_index), (-1, total_row_index), colors.HexColor('#e8e8e8')))
    base_style.append(('FONTNAME', (0, total_row_index), (-1, total_row_index), 'Helvetica-Bold'))

    for row_idx in row_debit_cols:
        base_style.append(('TEXTCOLOR', (8, row_idx), (8, row_idx), colors.red))
        base_style.append(('FONTNAME', (8, row_idx), (8, row_idx), 'Helvetica-Bold'))

    for row_idx in row_credit_cols:
        base_style.append(('TEXTCOLOR', (9, row_idx), (9, row_idx), colors.HexColor('#1a56db')))
        base_style.append(('FONTNAME', (9, row_idx), (9, row_idx), 'Helvetica-Bold'))

    for row_idx, bal_color in row_balance_colors:
        base_style.append(('TEXTCOLOR', (10, row_idx), (10, row_idx), bal_color))
        base_style.append(('FONTNAME', (10, row_idx), (10, row_idx), 'Helvetica-Bold'))

    table.setStyle(TableStyle(base_style))
    elements.append(table)

    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}", title_style))

    doc.build(elements)
    return response


# ==============================
# 🔹 URDU PDF (HTML + WeasyPrint)
# ==============================
@login_required
def generate_pdf_urdu(request, party_id):
    # Check subscription access
    if not check_subscription_access(request.user):
        messages.warning(request, 'Please subscribe to continue.')
        return redirect('subscribe')

    if not WEASYPRINT_AVAILABLE:
        messages.warning(request, 'Urdu PDF not available. Install weasyprint for Urdu support.')
        return generate_pdf_english(request, party_id)

    party = get_object_or_404(Party, id=party_id, user=request.user)
    transactions = Transaction.objects.filter(party=party).order_by('date', 'id')

    room_no = request.GET.get('room_no')
    if room_no:
        transactions = transactions.filter(room_no=room_no)

    shop_name = party.shop_name if party.shop_name else ''

    total_rokad = sum(t.rokad for t in transactions)
    total_ant = sum(t.ant for t in transactions)

    html_string = render_to_string('party_pdf_urdu.html', {
        'party': party,
        'transactions': transactions,
        'room_no': room_no,
        'shop_name': shop_name,
        'total_rokad': total_rokad,
        'total_ant': total_ant,
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"{party.name}_account_urdu.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    HTML(string=html_string).write_pdf(response)
    return response


# ==============================
# 🔹 PARTY SUMMARY API
# ==============================
from django.http import JsonResponse

@login_required
def get_party_summary(request, party_id):
    """Return party summary as JSON for speech and display"""
    party = get_object_or_404(Party, id=party_id, user=request.user)

    lang = request.GET.get('lang', 'en')

    recent_transactions = Transaction.objects.filter(
        party=party
    ).order_by('-date', '-id')[:5]

    if lang == 'ur':
        if party.balance > 0:
            balance_status = f"آپ کے ذمہ {abs(party.balance):,.0f} روپے ہیں"
            balance_direction = "payable"
        elif party.balance < 0:
            balance_status = f"پارٹی کے ذمہ {abs(party.balance):,.0f} روپے ہیں"
            balance_direction = "receivable"
        else:
            balance_status = "کوئی بقایا نہیں ہے"
            balance_direction = "clear"

        summary = f"""**خلاصہ حساب - {party.name}**

📊 **حساب کتاب کا خلاصہ:**
• کل جمع (وصول کردہ): {party.total_credit:,.0f} روپے
• کل نام (دیے گئے): {party.total_debit:,.0f} روپے
• **موجودہ بیلنس:** {abs(party.balance):,.0f} روپے ({balance_status})

📅 **حالیہ لین دین:**
"""
        for trans in recent_transactions:
            trans_date = trans.date.strftime('%d/%m/%Y')
            if trans.debit > 0:
                summary += f"• {trans_date}: {trans.debit:,.0f} روپے (نام)"
                if trans.commission > 0:
                    summary += f" - کمیشن: {trans.commission:,.0f}"
                if trans.bharti > 0:
                    summary += f" - بھرتی: {trans.bharti:,.3f} KG"
                summary += f" - {trans.note or 'تفصیل موجود نہیں'}\n"
            else:
                summary += f"• {trans_date}: {trans.credit:,.0f} روپے (جمع)"
                if trans.commission > 0:
                    summary += f" - کمیشن: {trans.commission:,.0f}"
                if trans.bharti > 0:
                    summary += f" - بھرتی: {trans.bharti:,.3f} KG"
                summary += f" - {trans.note or 'تفصیل موجود نہیں'}\n"

        summary += f"\n💡 **نوٹ:** {balance_status}۔ برائے مہربانی وقت پر تصفیہ فرمائیں۔"

    elif lang == 'pa':
        if party.balance > 0:
            balance_status = f"ਤੁਹਾਡੇ ਜ਼ਿੰਮੇ {abs(party.balance):,.0f} ਰੁਪਏ ਹਨ"
            balance_direction = "payable"
        elif party.balance < 0:
            balance_status = f"ਪਾਰਟੀ ਦੇ ਜ਼ਿੰਮੇ {abs(party.balance):,.0f} ਰੁਪਏ ਹਨ"
            balance_direction = "receivable"
        else:
            balance_status = "ਕੋਈ ਬਕਾਇਆ ਨਹੀਂ ਹੈ"
            balance_direction = "clear"

        summary = f"""**ਹਿਸਾਬ ਕਿਤਾਬ ਦਾ ਸੰਖੇਪ - {party.name}**

📊 **ਹਿਸਾਬ ਦਾ ਸੰਖੇਪ:**
• ਕੁੱਲ ਜਮ੍ਹਾ (ਪ੍ਰਾਪਤ): {party.total_credit:,.0f} ਰੁਪਏ
• ਕੁੱਲ ਨਾਮ (ਦਿੱਤੇ): {party.total_debit:,.0f} ਰੁਪਏ
• **ਮੌਜੂਦਾ ਬਕਾਇਆ:** {abs(party.balance):,.0f} ਰੁਪਏ ({balance_status})

📅 **ਹਾਲੀਆ ਲੈਣ-ਦੇਣ:**
"""
        for trans in recent_transactions:
            trans_date = trans.date.strftime('%d/%m/%Y')
            if trans.debit > 0:
                summary += f"• {trans_date}: {trans.debit:,.0f} ਰੁਪਏ (ਨਾਮ)"
                if trans.commission > 0:
                    summary += f" - ਕਮਿਸ਼ਨ: {trans.commission:,.0f}"
                if trans.bharti > 0:
                    summary += f" - ਭਰਤੀ: {trans.bharti:,.3f} KG"
                summary += f" - {trans.note or 'ਕੋਈ ਵੇਰਵਾ ਨਹੀਂ'}\n"
            else:
                summary += f"• {trans_date}: {trans.credit:,.0f} ਰੁਪਏ (ਜਮ੍ਹਾ)"
                if trans.commission > 0:
                    summary += f" - ਕਮਿਸ਼ਨ: {trans.commission:,.0f}"
                if trans.bharti > 0:
                    summary += f" - ਭਰਤੀ: {trans.bharti:,.3f} KG"
                summary += f" - {trans.note or 'ਕੋਈ ਵੇਰਵਾ ਨਹੀਂ'}\n"

        summary += f"\n💡 **ਨੋਟ:** {balance_status}। ਕਿਰਪਾ ਕਰਕੇ ਸਮੇਂ ਸਿਰ ਨਿਪਟਾਰਾ ਕਰੋ۔"

    else:
        if party.balance > 0:
            balance_status = f"Payable: {abs(party.balance):,.0f} rupees"
            balance_direction = "payable"
        elif party.balance < 0:
            balance_status = f"Receivable: {abs(party.balance):,.0f} rupees"
            balance_direction = "receivable"
        else:
            balance_status = "No outstanding balance"
            balance_direction = "clear"

        summary = f"""**ACCOUNT SUMMARY - {party.name}**

📊 **Financial Overview:**
• Total Credit (Received): {party.total_credit:,.0f} rupees
• Total Debit (Given): {party.total_debit:,.0f} rupees
• **Current Balance:** {abs(party.balance):,.0f} rupees ({balance_status})

📅 **Recent Transactions:**
"""
        for trans in recent_transactions:
            trans_date = trans.date.strftime('%d/%m/%Y')
            if trans.debit > 0:
                summary += f"• {trans_date}: {trans.debit:,.0f} rupees (Debit)"
                if trans.commission > 0:
                    summary += f" - Commission: {trans.commission:,.0f}"
                if trans.bharti > 0:
                    summary += f" - Weight: {trans.bharti:,.3f} KG"
                summary += f" - {trans.note or 'No description'}\n"
            else:
                summary += f"• {trans_date}: {trans.credit:,.0f} rupees (Credit)"
                if trans.commission > 0:
                    summary += f" - Commission: {trans.commission:,.0f}"
                if trans.bharti > 0:
                    summary += f" - Weight: {trans.bharti:,.3f} KG"
                summary += f" - {trans.note or 'No description'}\n"

        summary += f"\n💡 **Note:** {balance_status}. Please settle the amount at your earliest convenience."

    slip_data = {
        'party_name': party.name,
        'total_credit': f"{party.total_credit:,.0f}",
        'total_debit': f"{party.total_debit:,.0f}",
        'balance': f"{abs(party.balance):,.0f}",
        'balance_status': balance_status,
        'balance_direction': balance_direction,
        'recent_transactions': [
            {
                'date': trans.date.strftime('%d/%m/%Y'),
                'amount': f"{trans.debit if trans.debit > 0 else trans.credit:,.0f}",
                'type': 'Debit' if trans.debit > 0 else 'Credit',
                'type_ur': 'نام' if trans.debit > 0 else 'جمع',
                'commission': f"{trans.commission:,.0f}" if trans.commission > 0 else None,
                'bharti': f"{trans.bharti:,.3f}" if trans.bharti > 0 else None,
                'note': trans.note or '—'
            }
            for trans in recent_transactions
        ],
        'generated_at': timezone.now().strftime('%d/%m/%Y %H:%M')
    }

    return JsonResponse({
        'summary': summary,
        'balance': float(party.balance),
        'name': party.name,
        'slip_data': slip_data,
        'summary_text': summary.replace('**', '').replace('•', '-'),
    })
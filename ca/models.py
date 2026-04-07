from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import timedelta

# ==============================
# 🔹 PARTY MODEL
# ==============================
class Party(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parties')

    name = models.CharField(max_length=150, verbose_name=_("نام"))
    cnic = models.CharField(max_length=15, blank=True, null=True, verbose_name=_("شناختی کارڈ نمبر"))
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("فون نمبر"))
    address = models.TextField(blank=True, null=True, verbose_name=_("پتہ"))
    shop_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="دکان کا نام / Shop Name")
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("کل نام"))
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("کل جمع"))
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, editable=False, verbose_name=_("بیلنس"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.balance = self.total_credit - self.total_debit
        super().save(*args, **kwargs)

    @property
    def balance_color(self):
        if self.balance < 0:
            return 'red'
        return 'blue'

    class Meta:
        ordering = ['name']
        verbose_name = _("کھاتہ دار")
        verbose_name_plural = _("کھاتہ دار")


# ==============================
# 🔹 TRANSACTION MODEL
# ==============================
class Transaction(models.Model):
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='transactions')

    date = models.DateField(default=timezone.now, verbose_name=_("تاریخ / Date"))
    room_no = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("روم نمبر / Room No"))

    product_name = models.CharField(max_length=300, blank=True, null=True, verbose_name=_("اشیاء / تفصیل"))
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name=_("تعداد / Qty"))
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_("ریٹ / Rate"))

    commission = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("کمیشن / Commission"))
    bharti = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name=_("بھرتی (KG) / Weight"))
    ant = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("انت / Net Amount"))

    rokad = models.DecimalField(max_digits=15, decimal_places=2, default=0, blank=True, verbose_name=_("روکڑ / Cash"))

    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("نام / Debit"))
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name=_("جمع / Credit"))

    reference = models.TextField(blank=True, null=True, verbose_name=_("حوالہ / Reference"))
    note = models.TextField(blank=True, null=True, verbose_name=_("نوٹ / Note"))

    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, editable=False, verbose_name=_("بیلنس / Balance"))

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.party.name} - {self.date}"

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(_("ایک ٹرانزیکشن میں صرف ایک ہی ہو سکتا ہے — نام یا جمع"))
        if self.debit == 0 and self.credit == 0:
            raise ValidationError(_("نام یا جمع میں سے ایک ضرور بھریں"))

    def save(self, *args, **kwargs):
        if self.ant > 0:
            if self.debit > 0:
                self.debit = self.ant
            elif self.credit > 0:
                self.credit = self.ant

        if not self.pk:
            last_transaction = Transaction.objects.filter(
                party=self.party
            ).order_by('-date', '-id').first()

            previous_balance = last_transaction.balance if last_transaction else Decimal('0')

            self.balance = previous_balance + (self.credit - self.debit)

            self.party.total_debit += self.debit
            self.party.total_credit += self.credit
            self.party.save()

        super().save(*args, **kwargs)

    @property
    def row_color(self):
        if self.debit > 0:
            return 'red'
        return 'blue'

    @property
    def balance_color(self):
        if self.balance < 0:
            return 'red'
        elif self.balance > 0:
            return 'blue'
        return 'black'

    @property
    def transaction_type_ur(self):
        if self.debit > 0:
            return 'نام'
        return 'جمع'

    @property
    def transaction_type_en(self):
        if self.debit > 0:
            return 'Naam (Debit)'
        return 'Jama (Credit)'

    @property
    def debit_display(self):
        return self.debit if self.debit > 0 else ''

    @property
    def credit_display(self):
        return self.credit if self.credit > 0 else ''

    class Meta:
        ordering = ['date', 'id']
        verbose_name = _("ٹرانزیکشن")
        verbose_name_plural = _("ٹرانزیکشنز")


# ==============================
# 🔹 SUBSCRIPTION MODEL (NO TRIAL)
# ==============================
class UserProfile(models.Model):
    """User subscription information - NO FREE TRIAL"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # ✅ Subscription fields only (NO trial fields)
    is_subscribed = models.BooleanField(default=False)
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)

    # Payment screenshot (optional)
    payment_screenshot = models.ImageField(upload_to='payments/', null=True, blank=True)
    payment_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Subscribed: {self.is_subscribed}"

    def has_active_access(self):
        """Check if user has active subscription"""
        # Only check subscription, NO trial
        if self.is_subscribed and self.subscription_end_date:
            if self.subscription_end_date > timezone.now():
                return True
        return False

    def get_subscription_remaining_days(self):
        """Return remaining subscription days"""
        if self.subscription_end_date:
            remaining = (self.subscription_end_date - timezone.now()).days
            return max(0, remaining)
        return 0

    def activate_subscription(self, months=1):
        """Activate subscription for given months"""
        self.is_subscribed = True
        self.subscription_start_date = timezone.now()
        self.subscription_end_date = timezone.now() + timedelta(days=30 * months)
        self.save()

    def deactivate_subscription(self):
        """Deactivate subscription"""
        self.is_subscribed = False
        self.subscription_end_date = None
        self.subscription_start_date = None
        self.save()

    class Meta:
        verbose_name = _("صارف سبسکرپشن")
        verbose_name_plural = _("صارف سبسکرپشنز")
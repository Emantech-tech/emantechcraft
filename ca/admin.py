from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from .models import Party, Transaction, UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

# ==============================
# 🔹 PARTY ADMIN
# ==============================
@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'shop_name', 'total_debit', 'total_credit', 'balance', 'balance_color_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone', 'cnic', 'shop_name')
    readonly_fields = ('total_debit', 'total_credit', 'balance', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'phone', 'cnic', 'address', 'shop_name')
        }),
        ('Financial Summary', {
            'fields': ('total_debit', 'total_credit', 'balance'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def balance_color_display(self, obj):
        color = 'red' if obj.balance < 0 else 'blue' if obj.balance > 0 else 'black'
        return format_html(f'<span style="color: {color}; font-weight: bold;">₨ {obj.balance:,.2f}</span>')
    balance_color_display.short_description = 'Balance'


# ==============================
# 🔹 TRANSACTION ADMIN
# ==============================
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'party', 'date', 'product_name', 'qty', 'rate', 'commission', 'bharti', 'ant', 'rokad', 'debit', 'credit', 'balance_color_display', 'created_at')
    list_filter = ('date', 'party', 'room_no')
    search_fields = ('party__name', 'product_name', 'reference', 'room_no')
    readonly_fields = ('balance', 'created_at')

    fieldsets = (
        ('Transaction Info', {
            'fields': ('party', 'date', 'room_no')
        }),
        ('Product Details', {
            'fields': ('product_name', 'qty', 'rate')
        }),
        ('Financial Fields', {
            'fields': ('commission', 'bharti', 'ant', 'rokad', 'debit', 'credit'),
            'description': 'Commission, Bharti (KG), Ant (Net Amount)'
        }),
        ('Additional Info', {
            'fields': ('reference', 'note', 'balance'),
            'classes': ('collapse',)
        }),
    )

    def balance_color_display(self, obj):
        if obj.balance < 0:
            color = 'red'
        elif obj.balance > 0:
            color = 'blue'
        else:
            color = 'black'
        return format_html(f'<span style="color: {color}; font-weight: bold;">₨ {obj.balance:,.2f}</span>')
    balance_color_display.short_description = 'Balance'


# ==============================
# 🔹 USER PROFILE ADMIN (SUBSCRIPTION ONLY - NO TRIAL)
# ==============================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_subscribed', 'subscription_status', 'subscription_end_date', 'payment_verified', 'has_active_access_display')
    list_filter = ('is_subscribed', 'payment_verified', 'subscription_end_date')
    search_fields = ('user__username', 'user__email')
    list_editable = ('is_subscribed', 'payment_verified')
    readonly_fields = ('subscription_start_date', 'created_at', 'updated_at')

    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Subscription Information', {
            'fields': ('is_subscribed', 'subscription_start_date', 'subscription_end_date'),
        }),
        ('Payment Verification', {
            'fields': ('payment_screenshot', 'payment_verified'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def subscription_status(self, obj):
        if obj.is_subscribed and obj.subscription_end_date:
            if obj.subscription_end_date > timezone.now():
                remaining = (obj.subscription_end_date - timezone.now()).days
                return format_html(f'<span style="color: green;">✅ Active ({remaining} days left)</span>')
            else:
                return format_html(f'<span style="color: red;">❌ Expired</span>')
        elif obj.is_subscribed and not obj.subscription_end_date:
            return format_html('<span style="color: orange;">⚠️ Active (No end date)</span>')
        return format_html('<span style="color: gray;">❌ Not subscribed</span>')
    subscription_status.short_description = 'Subscription Status'

    def has_active_access_display(self, obj):
        if obj.has_active_access():
            return format_html('<span style="color: green;">✅ Yes</span>')
        return format_html('<span style="color: red;">❌ No</span>')
    has_active_access_display.short_description = 'Active Access'

    # ✅ Auto set subscription expiry when is_subscribed is checked
    def save_model(self, request, obj, form, change):
        # Agar is_subscribed tick kiya gaya aur end date nahi hai
        if obj.is_subscribed and not obj.subscription_end_date:
            obj.subscription_start_date = timezone.now()
            obj.subscription_end_date = timezone.now() + timedelta(days=30)  # 30 days subscription
        # Agar is_subscribed unchecked kiya to end date clear karo
        elif not obj.is_subscribed and obj.subscription_end_date:
            obj.subscription_end_date = None
            obj.subscription_start_date = None
        super().save_model(request, obj, form, change)

    actions = ['activate_subscription_1month', 'activate_subscription_3months', 'deactivate_subscription']

    def activate_subscription_1month(self, request, queryset):
        for profile in queryset:
            profile.is_subscribed = True
            profile.subscription_start_date = timezone.now()
            profile.subscription_end_date = timezone.now() + timedelta(days=30)
            profile.save()
        self.message_user(request, f'{queryset.count} user(s) subscription activated for 1 month.')
    activate_subscription_1month.short_description = 'Activate Subscription (1 Month)'

    def activate_subscription_3months(self, request, queryset):
        for profile in queryset:
            profile.is_subscribed = True
            profile.subscription_start_date = timezone.now()
            profile.subscription_end_date = timezone.now() + timedelta(days=90)
            profile.save()
        self.message_user(request, f'{queryset.count} user(s) subscription activated for 3 months.')
    activate_subscription_3months.short_description = 'Activate Subscription (3 Months)'

    def deactivate_subscription(self, request, queryset):
        for profile in queryset:
            profile.is_subscribed = False
            profile.subscription_end_date = None
            profile.subscription_start_date = None
            profile.save()
        self.message_user(request, f'{queryset.count} user(s) subscription deactivated.')
    deactivate_subscription.short_description = 'Deactivate Subscription'


# ==============================
# 🔹 CUSTOM USER ADMIN (to show profile link)
# ==============================
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Subscription Profile'

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'has_subscription')

    def has_subscription(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.is_subscribed
        return False
    has_subscription.boolean = True
    has_subscription.short_description = 'Subscribed'

# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ==============================
# 🔹 SITE HEADER CONFIGURATION
# ==============================
admin.site.site_header = "Munshi Management System"
admin.site.site_title = "Munshi Admin Panel"
admin.site.index_title = "Welcome to Munshi Admin Dashboard"
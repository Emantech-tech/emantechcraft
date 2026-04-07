from django.urls import path, include
from . import views

urlpatterns = [
    # Auth URLs
    path('', views.intro_slip, name='intro_slip'),
    path('landing/', views.landing, name='landing'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
     path('send-otp/', views.send_otp_view, name='send_otp'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('api/check-subscription-status/', views.check_subscription_status, name='check_subscription_status'),
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Party URLs
    path('add-party/', views.add_party, name='add_party'),
    path('party/<int:id>/', views.party_detail, name='party_detail'),
    path('edit-party/<int:id>/', views.edit_party, name='edit_party'),
    path('delete-party/<int:id>/', views.delete_party, name='delete_party'),

    path('subscribe/', views.subscribe_view, name='subscribe'),
path('admin/activate-subscription/<int:user_id>/', views.activate_subscription_manual, name='activate_subscription'),
    path('add-transaction/<int:party_id>/', views.add_transaction, name='add_transaction'),
    path('edit-transaction/<int:pk>/', views.edit_transaction, name='edit_transaction'),
    path('delete-transaction/<int:transaction_id>/', views.delete_transaction, name='delete_transaction'),
    path('party/<int:party_id>/pdf/en/', views.generate_pdf_english, name='generate_pdf_english'),
    path('party/<int:party_id>/pdf/ur/', views.generate_pdf_urdu, name='generate_pdf_urdu'),
    path('api/party-summary/<int:party_id>/', views.get_party_summary, name='party_summary'),
]
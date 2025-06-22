from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='webhook-dashboard'),
    path('transactions/', views.transaction_list, name='transaction-list'),
    path('transactions/<int:pk>/', views.transaction_detail, name='transaction-detail'),
    path('transactions/<int:pk>/logs/', views.transaction_logs, name='transaction-logs'),
    path('webhook/', views.webhook_receiver, name='webhook-receiver'),
]
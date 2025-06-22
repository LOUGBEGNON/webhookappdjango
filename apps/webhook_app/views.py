import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .services import process_transaction
# views.py
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import WebhookTransaction, TransactionLog
import json

# logger = logging.getLogger(__name__)

logger = logging.getLogger('webhook_app')

@csrf_exempt
@require_POST
def webhook_receiver(request):
    logger.debug("=== TEST LOG MESSAGE ===")
    logger.debug(f"Request headers: {dict(request.headers)}")
    logger.debug(f"Raw body: {request.body.decode('utf-8')}")
    # Initialisation des variables
    raw_body = request.body.decode('utf-8')
    headers = dict(request.headers)
    transaction_id = None
    payload = None
    error = None

    # 1. Enregistrement initial de la réception
    try:
        # Tentative de parsing du JSON
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError as e:
            payload = {'raw_body': raw_body}
            error = f"JSON decode error: {str(e)}"
            logger.warning(error)

        # Récupération du transaction_id depuis différentes sources possibles
        transaction_id = (
            payload.get('reference') or
            payload.get('id') or
            headers.get('X-Transaction-ID') or
            headers.get('X-Request-ID') or
            f"NO_ID_{WebhookTransaction.objects.count() + 1}"
        )

        # 2. Création de la transaction (même avec des données partielles)
        transaction = WebhookTransaction.objects.create(
            transaction_id=transaction_id,
            payload=payload or {'error': 'empty_payload'},
            headers=headers,
            status='received',
            error_message=error
        )

        # Journalisation
        log_message = 'Webhook received' if not error else f'Webhook received with issues: {error}'
        TransactionLog.objects.create(
            transaction=transaction,
            level='warning' if error else 'info',
            message=log_message,
            details={
                'action': 'reception',
                'error': error,
                'raw_body_length': len(raw_body)
            }
        )

        # 3. Traitement asynchrone seulement si le payload est valide
        if not error and payload:
            process_transaction(transaction.id)
            return JsonResponse({'status': 'received', 'transaction_id': transaction_id}, status=202)
        else:
            return JsonResponse({
                'status': 'received_with_errors',
                'transaction_id': transaction_id,
                'warning': error or 'Partial data received'
            }, status=202)

    except Exception as e:
        # Gestion des erreurs critiques
        error_msg = f"Critical processing error: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Tentative de sauvegarde même en cas d'erreur critique
        try:
            if 'transaction' not in locals():
                transaction = WebhookTransaction.objects.create(
                    transaction_id=f"ERROR_{WebhookTransaction.objects.count() + 1}",
                    payload={'raw_body': raw_body[:1000]},  # Truncate if too large
                    headers=headers,
                    status='failed',
                    error_message=error_msg
                )

            TransactionLog.objects.create(
                transaction=transaction,
                level='critical',
                message='Webhook processing failed',
                details={
                    'error': error_msg,
                    'exception_type': str(type(e))
                }
            )
        except Exception as db_error:
            logger.critical(f"Failed to save error to database: {str(db_error)}")

        return JsonResponse({
            'status': 'error',
            'message': 'Webhook recorded but processing failed'
        }, status=500)

def dashboard(request):
    stats = {
        'received': WebhookTransaction.objects.count(),
        'processed': WebhookTransaction.objects.filter(status='processed').count(),
        'processing': WebhookTransaction.objects.filter(status='processing').count(),
        'failed': WebhookTransaction.objects.filter(status='failed').count(),
    }

    recent_transactions = WebhookTransaction.objects.order_by('-received_at')[:10]

    return render(request, 'webhook_app/dashboard.html', {
        'stats': stats,
        'recent_transactions': recent_transactions
    })


def transaction_list(request):
    transactions = WebhookTransaction.objects.all().order_by('-received_at')

    # Filtrage
    status = request.GET.get('status')
    if status:
        transactions = transactions.filter(status=status)

    date_from = request.GET.get('date_from')
    if date_from:
        transactions = transactions.filter(received_at__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        transactions = transactions.filter(received_at__lte=date_to)

    # Pagination
    paginator = Paginator(transactions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'webhook_app/transaction_list.html', {
        'transactions': page_obj,
        'status_choices': WebhookTransaction.STATUS_CHOICES,
        'paginator': paginator,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1
    })


def transaction_detail(request, pk):
    transaction = get_object_or_404(WebhookTransaction, pk=pk)

    try:
        payload_json = json.dumps(transaction.payload, indent=2)
    except:
        payload_json = str(transaction.payload)

    try:
        headers_json = json.dumps(transaction.headers, indent=2)
    except:
        headers_json = str(transaction.headers)

    return render(request, 'webhook_app/transaction_detail.html', {
        'transaction': transaction,
        'payload_json': payload_json,
        'headers_json': headers_json
    })


def transaction_logs(request, pk):
    transaction = get_object_or_404(WebhookTransaction, pk=pk)
    logs = transaction.logs.all().order_by('timestamp')

    # Préparation des données JSON pour l'affichage
    for log in logs:
        try:
            log.details_json = json.dumps(log.details, indent=2)
        except:
            log.details_json = str(log.details)

    return render(request, 'webhook_app/transaction_logs.html', {
        'transaction': transaction,
        'logs': logs
    })
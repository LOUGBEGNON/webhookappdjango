import logging
from django.utils import timezone
from .models import WebhookTransaction, TransactionLog

logger = logging.getLogger(__name__)


def process_transaction(transaction_id):
    """
    Version synchrone du traitement des transactions
    """
    try:
        # Récupération de la transaction
        transaction = WebhookTransaction.objects.get(id=transaction_id)

        # Mise à jour du statut
        transaction.status = 'processing'
        transaction.save()

        # Journalisation
        TransactionLog.objects.create(
            transaction=transaction,
            level='info',
            message='Started processing transaction',
            details={'mode': 'synchronous'}  # Plus de task_id car on n'utilise plus Celery
        )

        # =============================================
        # VOTRE LOGIQUE DE TRAITEMENT (à conserver)
        # =============================================
        payload = transaction.payload

        # Exemple basique de traitement :
        if 'amount' in payload:
            logger.info(f"Processing amount: {payload['amount']}")

        # ... votre code métier ici ...
        # =============================================

        # Mise à jour finale
        transaction.status = 'processed'
        transaction.processed_at = timezone.now()
        transaction.save()

        TransactionLog.objects.create(
            transaction=transaction,
            level='info',
            message='Transaction processed successfully',
            details={'result': 'success'}
        )

        return True

    except WebhookTransaction.DoesNotExist:
        error_msg = f"Transaction {transaction_id} not found"
        logger.error(error_msg)

        # Création d'une entrée d'erreur si la transaction n'existe pas
        fake_transaction = WebhookTransaction.objects.create(
            transaction_id=f"MISSING_{transaction_id}",
            payload={'error': error_msg},
            status='failed',
            error_message=error_msg
        )

        TransactionLog.objects.create(
            transaction=fake_transaction,
            level='error',
            message=error_msg,
            details={'error': error_msg}
        )
        return False

    except Exception as e:
        error_msg = f"Error processing transaction {transaction_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        if 'transaction' in locals():
            transaction.status = 'failed'
            transaction.error_message = str(e)
            transaction.save()

            TransactionLog.objects.create(
                transaction=transaction,
                level='error',
                message='Failed to process transaction',
                details={
                    'error': str(e),
                    'exception_type': type(e).__name__
                }
            )
        else:
            # Cas où même la récupération de la transaction a échoué
            WebhookTransaction.objects.create(
                transaction_id=f"ERROR_{transaction_id}",
                payload={'error': error_msg},
                status='failed',
                error_message=error_msg
            )

        return False
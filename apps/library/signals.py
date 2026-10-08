from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import DocumentVersion


@receiver(post_delete, sender=DocumentVersion)
def remove_file(sender, instance, **kwargs):
    """Al borrar una versión (o su documento, o a su dueño) se borra el archivo, pero solo si la transacción se confirma."""
    name, storage = instance.file.name, instance.file.storage
    if name:
        transaction.on_commit(lambda: storage.delete(name))

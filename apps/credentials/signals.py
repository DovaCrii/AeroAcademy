"""El archivo de una credencial se borra siempre que se borra la fila: desde la vista, el admin o en cascada."""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Credential


@receiver(post_delete, sender=Credential)
def delete_private_file(sender, instance, **kwargs):
    name, storage = instance.file.name, instance.file.storage
    if name:
        # Solo si la transacción se confirma: si se revierte, la fila sigue apuntando al archivo.
        transaction.on_commit(lambda: storage.delete(name))

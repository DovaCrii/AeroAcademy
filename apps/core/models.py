from django.db import models


class TimeStampedModel(models.Model):
    """Campos comunes de todos los modelos (docs/MODELO_DATOS.md)."""

    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        abstract = True


class TaskRun(models.Model):
    """Última ejecución de una tarea programada o de mantenimiento (D42): una fila por tarea.

    La llena `apps.core.taskruns.record_run` desde los comandos de gestión. El Centro de administración la lee para
    decir «✓ hoy 07:00» o «! atrasada». `ok` vacío = en curso (o interrumpida). El resumen lleva solo cifras:
    nunca nombres, correos ni mensajes de error."""

    name = models.CharField("tarea", max_length=60, unique=True)
    started_at = models.DateTimeField("empezó", null=True, blank=True)
    finished_at = models.DateTimeField("terminó", null=True, blank=True)
    ok = models.BooleanField("terminó bien", null=True, blank=True)
    summary = models.CharField("resumen", max_length=200, blank=True)

    class Meta:
        verbose_name = "ejecución de tarea"
        verbose_name_plural = "ejecuciones de tareas"
        ordering = ["name"]

    def __str__(self):
        return self.name

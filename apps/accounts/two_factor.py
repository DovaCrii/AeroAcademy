"""Segundo factor para la puerta pública (D36): activación, verificación y códigos de recuperación."""

import secrets

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from . import ratelimit, totp
from .models import Person, TotpDevice

SESSION_KEY = "totp_ok"
RECOVERY_COUNT = 8
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
_SALT = "accounts.totp.recovery.v1"


def needs_second_factor(person: Person) -> bool:
    """Quien puede moderar o administrar no entra por la puerta pública solo con contraseña."""
    return person.is_staff or person.is_superuser or person.is_lead


def _confirmed(person: Person) -> TotpDevice | None:
    return TotpDevice.objects.filter(person=person, confirmed_at__isnull=False).first()


def is_enrolled(person: Person) -> bool:
    return _confirmed(person) is not None


def begin_enrollment(person: Person) -> TotpDevice:
    """Dispositivo de la persona; si no tiene, crea un secreto nuevo sin confirmar. Si ya está activado, no cambia nada."""
    device = _confirmed(person)
    if device is not None:
        return device
    device, _ = TotpDevice.objects.get_or_create(
        person=person, defaults={"secret": totp.new_secret()}
    )
    return device


def _hash_recovery(code: str) -> str:
    return salted_hmac(_SALT, totp.clean_code(code).lower()).hexdigest()


def _new_recovery_codes() -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(RECOVERY_COUNT)]


def confirm_enrollment(person: Person, code: str) -> list[str] | None:
    """Con un código correcto activa el segundo factor y devuelve los códigos de recuperación (se muestran una vez)."""
    device = TotpDevice.objects.filter(person=person, confirmed_at__isnull=True).first()
    if device is None:
        return None
    counter = totp.verify(device.secret, code)
    if counter is None:
        return None
    codes = _new_recovery_codes()
    device.confirmed_at = timezone.now()
    device.last_counter = counter
    device.recovery_hashes = [_hash_recovery(c) for c in codes]
    device.save(update_fields=["confirmed_at", "last_counter", "recovery_hashes", "updated_at"])
    return codes


def check_blocked(person: Person, ip: str) -> bool:
    return ratelimit.blocked("totp", str(person.pk), limit=MAX_FAILURES) or ratelimit.blocked(
        "totp-ip", ip, limit=MAX_FAILURES * 4
    )


def verify_login(person: Person, raw: str, ip: str = "") -> bool:
    """Código TOTP vigente (una sola vez) o un código de recuperación (se gasta). Cuenta los fallos."""
    if check_blocked(person, ip):
        return False
    ok = _verify(person, raw)
    if ok:
        ratelimit.clear("totp", str(person.pk))
    else:
        ratelimit.hit("totp", str(person.pk), window=WINDOW_SECONDS)
        ratelimit.hit("totp-ip", ip, window=WINDOW_SECONDS)
    return ok


@transaction.atomic
def _verify(person: Person, raw: str) -> bool:
    device = (
        TotpDevice.objects.select_for_update()
        .filter(person=person, confirmed_at__isnull=False)
        .first()
    )
    if device is None:
        return False
    code = totp.clean_code(raw)
    counter = totp.verify(device.secret, code, after_counter=device.last_counter)
    if counter is not None:
        device.last_counter = counter
        device.save(update_fields=["last_counter", "updated_at"])
        return True
    digest = _hash_recovery(code)
    for stored in device.recovery_hashes:
        if constant_time_compare(stored, digest):
            device.recovery_hashes = [h for h in device.recovery_hashes if h != stored]
            device.save(update_fields=["recovery_hashes", "updated_at"])
            return True
    return False


def regenerate_recovery(person: Person) -> list[str]:
    codes = _new_recovery_codes()
    TotpDevice.objects.filter(person=person, confirmed_at__isnull=False).update(
        recovery_hashes=[_hash_recovery(c) for c in codes]
    )
    return codes


def disable(person: Person) -> None:
    TotpDevice.objects.filter(person=person).delete()


def recovery_left(person: Person) -> int:
    device = _confirmed(person)
    return len(device.recovery_hashes) if device else 0

from datetime import timedelta
from math import ceil
import unicodedata
from django.db.models import F, Q
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import LoginThrottle

LIMIT = 5
WINDOW = timedelta(minutes=5)

def key_for(request):
    username = unicodedata.normalize("NFKC", request.POST.get("username", "").strip())
    # REMOTE_ADDR is the direct peer. Untrusted forwarding headers are ignored.
    return salted_hmac("accounts.login_throttle", request.META.get("REMOTE_ADDR", "") + "\0" + username, algorithm="sha256").hexdigest()

def remaining(key):
    now = timezone.now()
    LoginThrottle.objects.filter(started_at__lt=now-timedelta(days=1)).filter(Q(blocked_until__isnull=True)|Q(blocked_until__lte=now)).delete()
    record = LoginThrottle.objects.filter(key=key).first()
    if record and record.blocked_until and record.blocked_until > now:
        return max(1, ceil((record.blocked_until-now).total_seconds()))
    return 0

def failure(key):
    now = timezone.now()
    LoginThrottle.objects.get_or_create(key=key, defaults={"started_at":now})
    LoginThrottle.objects.filter(key=key).filter(Q(blocked_until__lte=now)|Q(blocked_until__isnull=True,started_at__lte=now-WINDOW)).update(failures=0,started_at=now,blocked_until=None)
    # Database-side increments avoid losing simultaneous failures.
    LoginThrottle.objects.filter(key=key,blocked_until__isnull=True).update(failures=F("failures")+1)
    LoginThrottle.objects.filter(key=key,failures__gte=LIMIT,blocked_until__isnull=True).update(blocked_until=now+WINDOW)
    return remaining(key)

def clear(key):
    LoginThrottle.objects.filter(key=key).delete()

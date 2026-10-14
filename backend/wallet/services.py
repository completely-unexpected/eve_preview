from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    MAX_AMOUNT, ROLLING_CATEGORIES, DepositAccount, DepositAccountRequest,
    DepositBonus, MoneyRequest, PointConversion, PointGrant, Wallet, WalletEntry,
)


def valid_amount(amount):
    try:
        value = int(amount)
    except (TypeError, ValueError):
        raise ValidationError("금액은 1 이상의 정수여야 합니다.")
    if str(value) != str(amount).strip() or not 1 <= value <= MAX_AMOUNT:
        raise ValidationError("금액은 1원 이상 1조 원 이하여야 합니다.")
    return value


def wallet_for(member):
    wallet, _ = Wallet.objects.get_or_create(member=member)
    return wallet


def entry(wallet, kind, reference, available=0, reserved=0, points=0):
    WalletEntry.objects.create(
        wallet=wallet, kind=kind, reference=reference,
        available_delta=available, reserved_delta=reserved, points_delta=points,
    )


@transaction.atomic
def request_money(member, kind, amount, bonus_id=None):
    if kind not in MoneyRequest.Kind.values:
        raise ValidationError("신청 종류가 올바르지 않습니다.")
    value = valid_amount(amount)
    option = None
    bonus_data = {}
    if kind == MoneyRequest.Kind.WITHDRAW and bonus_id not in (None, ""):
        raise ValidationError("출금에는 입금 보너스를 선택할 수 없습니다.")
    if kind == MoneyRequest.Kind.DEPOSIT:
        percent = Decimal("0")
        name = "보너스 없음"
        destination = DepositBonus.Destination.BALANCE
        rolling = {key: 100 for key, _ in ROLLING_CATEGORIES}
        if bonus_id not in (None, ""):
            try:
                option = DepositBonus.objects.select_for_update().get(pk=bonus_id, is_active=True)
            except (DepositBonus.DoesNotExist, ValueError, TypeError, OverflowError):
                raise ValidationError("선택한 입금 보너스를 사용할 수 없습니다. 새로고침해 주세요.")
            percent = option.bonus_percent
            name = option.name
            destination = option.destination
            rolling = option.rolling_values()
        bonus_data = {
            "bonus_name": name,
            "bonus_percent": percent,
            "bonus_amount": int(Decimal(value) * percent / Decimal("100")),
            "bonus_destination": destination,
            "rolling_snapshot": rolling,
        }

    wallet = wallet_for(member)
    if kind == MoneyRequest.Kind.WITHDRAW:
        changed = Wallet.objects.filter(
            pk=wallet.pk, available__gte=value, reserved__lte=MAX_AMOUNT - value,
        ).update(available=F("available") - value, reserved=F("reserved") + value)
        if not changed:
            raise ValidationError("출금 가능한 보유금액이 부족합니다.")
    record = MoneyRequest.objects.create(
        member=member, kind=kind, amount=value, bonus_option=option, **bonus_data,
    )
    if kind == MoneyRequest.Kind.WITHDRAW:
        entry(wallet, "withdraw_reserved", f"money:{record.pk}:reserved", available=-value, reserved=value)
    return record


@transaction.atomic
def decide(request_id, operator, approve):
    if not operator.is_active or not operator.is_staff or not operator.has_perm("wallet.change_moneyrequest"):
        raise ValidationError("신청 처리 권한이 없습니다.")
    record = MoneyRequest.objects.select_for_update().get(pk=request_id)
    if record.status != MoneyRequest.Status.PENDING:
        raise ValidationError("이미 처리된 신청입니다.")
    wallet = wallet_for(record.member)
    amount = record.amount
    if approve and record.kind == MoneyRequest.Kind.DEPOSIT:
        bonus_balance = record.bonus_amount if record.bonus_destination == DepositBonus.Destination.BALANCE else 0
        bonus_points = record.bonus_amount if record.bonus_destination == DepositBonus.Destination.POINTS else 0
        credit = amount + bonus_balance
        changed = Wallet.objects.filter(
            pk=wallet.pk, available__lte=MAX_AMOUNT - credit, points__lte=MAX_AMOUNT - bonus_points,
        ).update(available=F("available") + credit, points=F("points") + bonus_points)
        if not changed:
            raise ValidationError("입금과 보너스 지급 후 잔액 상한을 초과합니다.")
        entry(wallet, "deposit_approved", f"money:{record.pk}:approved", available=amount)
        if record.bonus_amount:
            entry(wallet, "deposit_bonus", f"money:{record.pk}:bonus", available=bonus_balance, points=bonus_points)
            if bonus_points:
                PointGrant.objects.create(
                    member=record.member, amount=bonus_points,
                    reason=f"입금 보너스: {record.bonus_name}"[:200], granted_by=operator,
                )
    elif record.kind == MoneyRequest.Kind.WITHDRAW:
        if approve:
            changed = Wallet.objects.filter(pk=wallet.pk, reserved__gte=amount).update(reserved=F("reserved") - amount)
            if not changed:
                raise ValidationError("출금 예약 금액을 확인할 수 없습니다.")
            entry(wallet, "withdraw_approved", f"money:{record.pk}:approved", reserved=-amount)
        else:
            changed = Wallet.objects.filter(
                pk=wallet.pk, reserved__gte=amount, available__lte=MAX_AMOUNT - amount,
            ).update(reserved=F("reserved") - amount, available=F("available") + amount)
            if not changed:
                raise ValidationError("출금 예약 금액을 되돌릴 수 없습니다.")
            entry(wallet, "withdraw_rejected", f"money:{record.pk}:rejected", reserved=-amount, available=amount)
    record.status = MoneyRequest.Status.APPROVED if approve else MoneyRequest.Status.REJECTED
    record.processed_at = timezone.now()
    record.processed_by = operator
    record.save(update_fields=["status", "processed_at", "processed_by"])
    return record


@transaction.atomic
def grant_points(member, amount, reason, operator):
    if not operator.is_active or not operator.is_staff or not operator.has_perm("wallet.add_pointgrant"):
        raise ValidationError("포인트 지급 권한이 없습니다.")
    value = valid_amount(amount)
    if not reason.strip():
        raise ValidationError("지급 사유를 입력해 주세요.")
    wallet = wallet_for(member)
    changed = Wallet.objects.filter(pk=wallet.pk, points__lte=MAX_AMOUNT - value).update(points=F("points") + value)
    if not changed:
        raise ValidationError("포인트 상한을 초과합니다.")
    grant = PointGrant.objects.create(member=member, amount=value, reason=reason.strip(), granted_by=operator)
    entry(wallet, "point_granted", f"grant:{grant.pk}", points=value)
    return grant


@transaction.atomic
def convert_points(member, amount):
    value = valid_amount(amount)
    wallet = wallet_for(member)
    changed = Wallet.objects.filter(
        pk=wallet.pk, points__gte=value, available__lte=MAX_AMOUNT - value,
    ).update(points=F("points") - value, available=F("available") + value)
    if not changed:
        raise ValidationError("전환할 포인트가 부족하거나 보유금액 상한을 초과합니다.")
    conversion = PointConversion.objects.create(member=member, points=value)
    entry(wallet, "point_converted", f"conversion:{conversion.pk}", available=value, points=-value)
    return conversion


@transaction.atomic
def request_deposit_account(member):
    record, _ = DepositAccountRequest.objects.get_or_create(member=member, status="pending")
    return record


@transaction.atomic
def reply_deposit_account(request_id, account_id, operator):
    if not operator.is_active or not operator.is_staff or not operator.has_perm("wallet.change_depositaccountrequest"):
        raise ValidationError("입금 계좌 안내 권한이 없습니다.")
    record = DepositAccountRequest.objects.select_for_update().get(pk=request_id)
    if record.status != "pending":
        raise ValidationError("이미 안내한 요청입니다.")
    try:
        account = DepositAccount.objects.select_for_update().get(pk=account_id, is_active=True)
    except DepositAccount.DoesNotExist:
        raise ValidationError("안내 가능한 계좌를 선택해 주세요.")
    record.account = account
    record.account_snapshot = {
        "bankName": account.bank_name, "accountNumber": account.account_number,
        "accountHolder": account.account_holder, "instructions": account.instructions,
    }
    record.status = "replied"
    record.responded_at = timezone.now()
    record.responded_by = operator
    record.save(update_fields=["account", "account_snapshot", "status", "responded_at", "responded_by"])
    return record

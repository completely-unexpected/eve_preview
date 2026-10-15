"""Manual, audited settlement of non-redeemable virtual-money simulations."""
from decimal import Decimal
from fractions import Fraction
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from wallet.models import MAX_AMOUNT, Wallet
from wallet.services import entry, wallet_for
from .models import DemoLeg, DemoSlip


@transaction.atomic
def settle(slip_id, operator, *, result=None, position=None):
    if not operator.is_active or not operator.is_staff or not operator.has_perm('sportsfeed.change_demoslip'):
        raise ValidationError('가상머니 테스트 정산 권한이 없습니다.')
    if result not in ('won', 'lost', 'void'):
        raise ValidationError('적중·미적중·취소 중 하나를 선택해 주세요.')
    slip = DemoSlip.objects.select_for_update().get(pk=slip_id)
    legs = list(DemoLeg.objects.select_for_update().filter(slip=slip).order_by('position'))
    if not legs or len(legs) != len(slip.legs):
        raise ValidationError('경기 선택 정보가 일치하지 않아 정산할 수 없습니다.')
    if position is None:
        targets = [leg for leg in legs if leg.result == 'pending']
    else:
        targets = [leg for leg in legs if leg.position == position]
        if not targets: raise ValidationError('선택한 경기가 없습니다.')
        if targets[0].result == result: return 0
        if targets[0].result != 'pending': raise ValidationError('처리한 결과는 변경할 수 없습니다.')
    if not targets: return 0
    if slip.status != 'pending': raise ValidationError('이미 정산된 접수입니다.')
    now = timezone.now()
    credit = 0
    for leg in targets:
        leg.result, leg.settled_at, leg.settled_by = result, now, operator
        leg.save(update_fields=['result', 'settled_at', 'settled_by'])
        if slip.mode == 'single':
            credit += int(slip.stake * Fraction(Decimal(leg.selection['price']))) if result == 'won' else slip.stake if result == 'void' else 0
    finished = all(leg.result != 'pending' for leg in legs)
    if finished:
        outcomes = {leg.result for leg in legs}
        if slip.mode == 'multi':
            if 'lost' in outcomes:
                credit = 0
                slip.status = 'lost'
            elif outcomes == {'void'}:
                credit = slip.stake
                slip.status = 'void'
            else:
                odds = Fraction(1)
                for leg in legs:
                    if leg.result == 'won': odds *= Fraction(Decimal(leg.selection['price']))
                credit = int(slip.stake * odds)
                slip.status = 'won'
        else:
            slip.status = next(iter(outcomes)) if len(outcomes) == 1 else 'mixed'
        slip.settled_at, slip.settled_by = now, operator
    wallet = wallet_for(slip.member)
    if credit:
        if not 0 < credit <= MAX_AMOUNT or not Wallet.objects.filter(pk=wallet.pk, available__lte=MAX_AMOUNT-credit).update(available=F('available')+credit):
            raise ValidationError('가상머니 잔액 상한을 초과해 정산을 취소했습니다.')
    # A unique audit record also exists for zero-credit results.
    reference = f'demo-result:{slip.pk}:{position}' if position is not None else f'demo-result:{slip.pk}:all'
    entry(wallet, 'demo_settlement', reference, available=credit)
    slip.credited_amount += credit
    slip.save(update_fields=['status', 'credited_amount', 'settled_at', 'settled_by'])
    return len(targets)

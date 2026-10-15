"""Free virtual-money simulation. No payment or cash redemption integration."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib.auth import get_user_model
from wallet.models import MAX_AMOUNT, Wallet
from wallet.services import entry, valid_amount, wallet_for
from .models import DemoLeg, DemoSlip, FeedSnapshot


def reject(message):
    raise ValidationError(message)


def serialize(slip):
    return {'id': slip.pk, 'source': slip.source, 'mode': slip.mode, 'stake': slip.stake,
            'totalStake': slip.total_stake, 'expectedReturn': slip.expected_return,
            'legs': [{**leg.selection, 'result': leg.result} for leg in slip.results.all()],
            'createdAt': slip.created_at.isoformat(), 'status': slip.status, 'virtualOnly': True,
            'creditedAmount': slip.credited_amount,
            'settledAt': slip.settled_at.isoformat() if slip.settled_at else None}


def submit(member, data, *, source='sports'):
    if not isinstance(data, dict): reject('요청 형식이 올바르지 않습니다.')
    try:
        token = UUID(str(data.get('requestId', '')))
        encoded = json.dumps({k: data.get(k) for k in ('mode', 'stake', 'picks')}, sort_keys=True, ensure_ascii=True)
    except (ValueError, TypeError, AttributeError): reject('접수 식별자가 올바르지 않습니다.')
    fingerprint = hashlib.sha256((('powerball:' if source == 'powerball' else '') + encoded).encode()).hexdigest()
    def existing():
        saved = DemoSlip.objects.filter(member=member, request_id=token).first()
        if saved and saved.fingerprint != fingerprint: reject('같은 접수 번호로 다른 내용을 보낼 수 없습니다.')
        return saved
    try:
        with transaction.atomic():
            current = get_user_model().objects.select_for_update().get(pk=member.pk)
            if not current.is_active or current.account_status != 'approved': reject('승인된 회원만 이용할 수 있습니다.')
            saved = existing()
            if saved: return saved
            mode = data.get('mode')
            if mode not in ('single', 'multi'): reject('싱글 또는 멀티를 선택해 주세요.')
            stake = valid_amount(data.get('stake'))
            picks = data.get('picks')
            if not isinstance(picks, list) or not 1 <= len(picks) <= 20: reject('1~20개 경기를 선택해 주세요.')
            if source == 'powerball':
                from catalog.models import Game
                from .powerball import current_board
                if not Game.objects.filter(slug='powerball', is_published=True).exists(): reject('현재 운영하지 않는 게임입니다.')
                events = {e['id']: e for e in current_board()['items']}
            else:
                snapshot = FeedSnapshot.objects.filter(pk=1).first()
                from catalog.odds import apply_prices
                events = {e['id']: e for e in apply_prices(snapshot.payload.get('items', []), 'sports')} if snapshot else {}
            limits = current.effective_limits()
            if not limits[mode + '_min'] <= stake <= limits[mode + '_max']: reject('회원의 최소·최대 이용한도를 확인해 주세요.')
            legs, seen, returns = [], set(), []
            combined = Fraction(1)
            for pick in picks:
                if not isinstance(pick, dict): reject('선택 정보가 올바르지 않습니다.')
                event_id = pick.get('eventId')
                if not isinstance(event_id, str) or event_id in seen: reject('한 경기에서는 한 항목만 선택할 수 있습니다.')
                seen.add(event_id)
                event = events.get(event_id)
                start = parse_datetime(event.get('startsAt', '')) if event else None
                if not event or not start or timezone.is_naive(start) or start <= timezone.now() or event.get('completed') or event.get('status') != 'scheduled':
                    reject('시작 전 경기만 테스트 접수할 수 있습니다. 경기 목록을 새로고침해 주세요.')
                if source == 'powerball' and parse_datetime(event['closesAt']) <= timezone.now(): reject('해당 회차는 마감되었습니다. 다음 회차를 선택해 주세요.')
                market_key = pick.get('market')
                if not isinstance(market_key, str) or 'lay' in market_key: reject('지원하지 않는 시장입니다.')
                outcome = None
                book_name = ''
                for book in event.get('bookmakers', []):
                    if book.get('key') != pick.get('bookKey'): continue
                    book_name = book.get('title', '')
                    for market in book.get('markets', []):
                        if market.get('key') != market_key: continue
                        for candidate in market.get('outcomes', []):
                            if all(candidate.get(k) == pick.get(k) for k in ('name', 'point', 'description')):
                                outcome = candidate
                if not outcome or outcome.get('price') != pick.get('price'): reject('배당이 변경되었거나 선택이 없습니다. 새로고침 후 다시 선택해 주세요.')
                try:
                    decimal = Decimal(outcome['price'])
                    if not decimal.is_finite() or not 1 < decimal <= 1000000: raise ValueError()
                    odd = Fraction(decimal)
                except (ValueError, InvalidOperation, TypeError): reject('배당 정보가 올바르지 않습니다.')
                combined *= odd
                returns.append(int(stake * odd))
                legs.append({'eventId': event_id, 'home': event['home'], 'away': event['away'],
                             'startsAt': event['startsAt'], 'league': event.get('league', ''),
                             'bookKey': pick['bookKey'], 'book': book_name, 'market': market_key, **outcome})
            total = stake * len(legs) if mode == 'single' else stake
            expected = sum(returns) if mode == 'single' else int(stake * combined)
            if total > MAX_AMOUNT or expected > MAX_AMOUNT: reject('계산 가능한 금액 한도를 초과했습니다.')
            if (any(v > limits['single_payout'] for v in returns) if mode == 'single' else expected > limits['multi_payout']):
                reject('최대 예상 당첨 한도를 초과했습니다.')
            wallet = wallet_for(current)
            if not Wallet.objects.filter(pk=wallet.pk, available__gte=total).update(available=F('available') - total):
                reject('사용 가능한 가상머니가 부족합니다.')
            slip = DemoSlip.objects.create(member=current, source=source, request_id=token, fingerprint=fingerprint, mode=mode,
                                          stake=stake, total_stake=total, expected_return=expected, legs=legs)
            created_legs = DemoLeg.objects.bulk_create([DemoLeg(slip=slip, position=i, selection=leg) for i, leg in enumerate(legs)])
            from activity.tracking import created as audit_created
            for leg in created_legs:
                audit_created(DemoLeg, leg, created=True)
            entry(wallet, 'demo_slip', f'demo-slip:{slip.pk}', available=-total)
            return slip
    except IntegrityError:
        saved = existing()
        if saved: return saved
        raise

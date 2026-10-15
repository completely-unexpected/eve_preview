// Shared by sports and Powerball carts. Amounts use integer arithmetic.
function createStakeControls({value = '', id = 'cart-stake', onChange, onMax, presets = [10000, 50000, 100000, 500000, 1000000]}) {
  const root = document.createElement('div');
  const row = document.createElement('div'); row.className = 'sb-stake-row';
  const input = document.createElement('input'); input.id = id; input.type = 'text'; input.inputMode = 'numeric'; input.autocomplete = 'off'; input.maxLength = 25; input.placeholder = '배팅금액'; input.setAttribute('aria-label', '배팅금액'); input.value = value;
  const stakeValue = () => {const digits = input.value.replace(/,/g, ''); return /^\d+$/.test(digits) && digits.length <= 13 ? BigInt(digits) : 0n;};
  const setStake = raw => {input.value = raw; input.dispatchEvent(new Event('input'));};
  for (const [symbol, delta] of [['−', -10000n], ['+', 10000n]]) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = symbol; button.setAttribute('aria-label', delta < 0 ? '금액 1만원 줄이기' : '금액 1만원 늘리기');
    button.onclick = () => setStake(String(stakeValue() + delta < 0n ? 0n : stakeValue() + delta)); row.append(button);
  }
  row.append(input); root.append(row);
  const choices = document.createElement('div'); choices.className = 'sb-stake-presets';
  for (const amount of presets) {const button = document.createElement('button'); button.type = 'button'; button.textContent = amount.toLocaleString('ko-KR'); button.onclick = () => setStake(String(amount)); choices.append(button);}
  const max = document.createElement('button'); max.type = 'button'; max.textContent = 'MAX'; max.onclick = () => {const amount = onMax(); if (amount !== null && amount !== undefined) setStake(String(amount));}; choices.append(max); root.append(choices);
  input.oninput = () => {
    const raw = input.value;
    if (!/^[0-9,]*$/.test(raw)) {onChange(raw, '금액은 숫자로 입력해 주세요.'); return;}
    const before = raw.slice(0, input.selectionStart ?? raw.length).replace(/,/g, '').length;
    const original = raw.replace(/,/g, ''); const digits = original.replace(/^0+(?=\d)/, '');
    input.value = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    let cursor = 0, consumed = 0; const target = Math.max(0, before - (original.length - digits.length));
    while (cursor < input.value.length && consumed < target) {if (input.value[cursor] !== ',') consumed++; cursor++;}
    input.setSelectionRange(cursor, cursor); onChange(input.value, '');
  };
  return {root, input, stakeValue, setStake};
}

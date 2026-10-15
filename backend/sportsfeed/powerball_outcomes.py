def outcomes(result):
    total=sum(result.balls)
    return {
        'general_parity':'홀' if total%2 else '짝',
        'general_range':'대 (81~130)' if total>=81 else '중 (65~80)' if total>=65 else '소 (15~64)',
        'power_parity':'홀' if result.powerball%2 else '짝',
        'power_range':'언더 (0~4)' if result.powerball<=4 else '오버 (5~9)',
    }

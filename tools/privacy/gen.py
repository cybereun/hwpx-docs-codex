"""Synthetic people for the privacy tests: fake names, valid check digits, no real person. Standard library only.

  person(seed) -> dict of fields; every number has a correct check digit where the kind has one.
  canaries(p)  -> [(kind, value)] the values that must never reach the model.

Names are random syllable combinations, addresses use invented road names, e-mail uses example.com (RFC 2606), IPs use 203.0.113.0/24
(TEST-NET-3). Phone and registration numbers are random: they are fake on purpose and only ever written on this PC.
"""
import datetime
import random

SURNAMES = list('김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민나진지엄채원천방공현')
GIVEN = list('민서준하지우연도현수은재윤진아예승시건유찬나율솔빈담온새한결휘')
ROADS = ['가온', '나래', '다솜', '마루', '바다', '새벽', '아침', '여울', '하늘', '미르', '라온', '두리']
SIDO = [('서울특별시', ['종로구', '마포구', '성동구']), ('경기도', ['성남시 분당구', '수원시 영통구', '고양시 일산동구']),
        ('부산광역시', ['해운대구', '수영구']), ('대구광역시', ['수성구']), ('전라남도', ['순천시']), ('강원특별자치도', ['춘천시'])]
BANKS = ['국민은행', '신한은행', '우리은행', '하나은행', '농협은행']
EMPLOYERS = ['(주)가온테크', '새봄병원', '한빛공단', '다솜재단']
SCHOOLS = ['한빛고등학교', '새봄대학교', '가온중학교']
SENSITIVE = [
    '저는 우울증으로 정신과 치료를 받고 있어 근무 조정을 요청합니다.',
    '신청인은 2019년 사기죄로 징역 1년에 집행유예를 선고받았음.',
    '본인은 교회 활동 때문에 일요일 근무가 어렵습니다.',
    '아이가 학교폭력 피해를 입어 상담 치료 중입니다.',
    '배우자는 암 진단을 받고 항암 치료 중이라 긴급복지 지원을 신청함.',
]
KINDS = ['name', 'rrn', 'phone', 'tel', 'email', 'address', 'bank', 'card', 'plate', 'passport', 'driving', 'brn', 'ip', 'employer', 'school']


def _rrn(rng, foreign=False):
    y = rng.randint(1950, 2004)
    m, d = rng.randint(1, 12), rng.randint(1, 28)
    g = (5 if y < 2000 else 7) if foreign else (1 if y < 2000 else 3)
    g += rng.randint(0, 1)
    base = f'{y % 100:02d}{m:02d}{d:02d}{g}{rng.randint(0, 99999):05d}'
    w = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)
    s = sum(int(a) * b for a, b in zip(base, w)) % 11
    c = ((13 if foreign else 11) - s) % 10
    return base[:6] + '-' + base[6:] + str(c), datetime.date(y, m, d)


def _luhn(prefix, n=16):
    body = prefix + ''.join(str(random.randint(0, 9)) for _ in range(n - len(prefix) - 1))
    t = 0
    for i, ch in enumerate(reversed(body)):
        v = int(ch)
        if i % 2 == 0:
            v = v * 2 - 9 if v > 4 else v * 2
        t += v
    return body + str((10 - t % 10) % 10)


def _brn(rng):
    d = [rng.randint(1, 9) for _ in range(3)] + [rng.choice([1, 2, 3, 4, 5, 90, 91]) for _ in range(1)]
    mid = f'{rng.choice([1, 2, 5, 7, 91]):02d}'
    nine = f'{rng.randint(100, 999)}{mid}{rng.randint(1000, 9999)}'
    w = (1, 3, 7, 1, 3, 7, 1, 3, 5)
    t = sum(int(a) * b for a, b in zip(nine, w)) + int(nine[8]) * 5 // 10
    return f'{nine[:3]}-{nine[3:5]}-{nine[5:]}{(10 - t % 10) % 10}'


def person(seed):
    rng = random.Random(seed)
    random.seed(seed)
    rrn, birth = _rrn(rng)
    sido, gu = rng.choice(SIDO)
    road = rng.choice(ROADS) + rng.choice(['로', '길'])
    num = f'{rng.randint(1, 500)}'
    detail = f'{rng.randint(101, 120)}동 {rng.randint(101, 2504)}호'
    card = _luhn(rng.choice(['4539', '5105', '4916']))
    p = {
        'seed': seed,
        'name': rng.choice(SURNAMES) + rng.choice(GIVEN) + rng.choice(GIVEN),
        'rrn': rrn, 'birth': birth.strftime('%Y.%m.%d'),
        'phone': f'010-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}',
        'tel': f'0{rng.choice([2, 31, 51])}-{rng.randint(200, 999)}-{rng.randint(1000, 9999)}',
        'address': f'{sido} {rng.choice(gu)} {road} {num}, {detail}',
        'postcode': f'{rng.randint(10000, 59999)}',
        'bank': f'{rng.choice(BANKS)} {rng.randint(100, 999)}-{rng.randint(100, 999)}-{rng.randint(100000, 999999)}',
        'card': '-'.join(card[i:i + 4] for i in range(0, 16, 4)),
        'plate': f'{rng.randint(10, 99)}{rng.choice("가나다라마거너더")} {rng.randint(1000, 9999)}',
        'passport': 'M' + ''.join(str(rng.randint(0, 9)) for _ in range(8)),
        'driving': f'{rng.choice(["11", "12", "13", "21", "26"])}-{rng.randint(10, 24)}-{rng.randint(100000, 999999)}-{rng.randint(10, 99)}',
        'brn': _brn(rng),
        'ip': f'203.0.113.{rng.randint(1, 254)}',
        'employer': rng.choice(EMPLOYERS), 'school': rng.choice(SCHOOLS),
        'sens': rng.choice(SENSITIVE),
    }
    p['email'] = f'user{rng.randint(1000, 9999)}@mail.example.com'
    p['bank_no'] = p['bank'].split(' ', 1)[1]
    frn, _ = _rrn(rng, foreign=True)
    n = lambda k: ''.join(str(rng.randint(0, 9)) for _ in range(k))
    p.update({
        'frn': frn, 'age': f'{rng.randint(20, 79)}세', 'nation': rng.choice(['대한민국', '베트남', '필리핀', '몽골']),
        'family': rng.choice(SURNAMES) + rng.choice(GIVEN) + rng.choice(GIVEN), 'mac': ':'.join(f'{rng.randint(0, 255):02X}' for _ in range(6)),
        'gps': f'{rng.uniform(33, 38):.6f}, {rng.uniform(126, 129):.6f}', 'handle': f'user_{n(5)}',
        'secret': f'pw{n(6)}', 'sec': f'{rng.randint(100, 999)}-{rng.randint(10, 99)}-{n(6)}',
        'wallet': '0x' + ''.join(rng.choice('0123456789abcdef') for _ in range(40)),
        'money': f'{rng.randint(10, 99)},{n(3)},{n(3)}원', 'credit': f'{rng.randint(600, 990)}점',
        'sid': '20' + n(8), 'eid': 'A' + n(7), 'mid': f'{rng.randint(10, 24)}-{n(8)}', 'exam': '2026' + n(6), 'chart': n(8),
        'hins': n(11), 'case': f'20{rng.randint(15, 25)}{rng.choice(["가합", "가단", "고단", "노"])}{rng.randint(1000, 99999)}',
        'petition': f'2AA-{rng.randint(2501, 2611)}-{n(7)}', 'member': f'M-{n(5)}', 'licence': f'{n(2)}-{n(2)}-{n(4)}',
        'idcard': f'20{rng.randint(10, 25)}-{n(6)}'})
    return p


def canaries(p):
    """[(kind, value)] to look for in outputs. Values that are only a word of a sentence (the sensitive sentence) are not listed here."""
    out = [('name', p['name']), ('rrn', p['rrn']), ('phone', p['phone']), ('tel', p['tel']), ('email', p['email']),
           ('address', p['address'].split(',')[0]), ('bank', p['bank_no']), ('card', p['card']), ('plate', p['plate']),
           ('passport', p['passport']), ('driving', p['driving']), ('brn', p['brn']), ('ip', p['ip']),
           ('employer', p['employer']), ('school', p['school'])]
    return out


if __name__ == '__main__':
    import json
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(person(int(sys.argv[1]) if len(sys.argv) > 1 else 1), ensure_ascii=False, indent=1, default=str))

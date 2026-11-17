"""Small validators and attribute rules that the packs name (`"check": "rrn"`, `"disclose": "rrn"`). Standard library only.

A validator takes the matched text and returns True / False. A discloser takes (matched text, line context) and returns
{'attrs': [(class, text)], 'status': text}: the coarse attributes the model may see, each with a class.
"""
import datetime
import re

DIGITS = re.compile(r'\D')


def digits(s):
    return DIGITS.sub('', s)


# ---- registration numbers -------------------------------------------------------------------------------------------
def _century(g):
    return {1: 1900, 2: 1900, 3: 2000, 4: 2000, 5: 1900, 6: 1900, 7: 2000, 8: 2000, 9: 1800, 0: 1800}[g]


def rrn_date(d):
    """(year, month, day, g) of a 13-digit number, or None when the date or the 7th digit is impossible."""
    if len(d) != 13:
        return None
    g = int(d[6])
    y, m, day = _century(g) + int(d[0:2]), int(d[2:4]), int(d[4:6])
    try:
        datetime.date(y, m, day)
    except ValueError:
        return None
    return y, m, day, g


def rrn_sum(d):
    w = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)
    return sum(int(a) * b for a, b in zip(d[:12], w)) % 11


def rrn_checksum_ok(d):
    return (11 - rrn_sum(d)) % 10 == int(d[12])


def frn_checksum_ok(d):
    return (13 - rrn_sum(d)) % 10 == int(d[12])


def rrn(s):
    d = digits(s)
    x = rrn_date(d)
    return bool(x) and x[3] in (1, 2, 3, 4, 9, 0)


def frn(s):
    d = digits(s)
    x = rrn_date(d)
    return bool(x) and x[3] in (5, 6, 7, 8)


def luhn(s):
    d = digits(s)
    if not 13 <= len(d) <= 19:
        return False
    t = 0
    for i, c in enumerate(reversed(d)):
        n = int(c)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        t += n
    return t % 10 == 0


def card(s):
    d = digits(s)
    return luhn(d) and d[0] in '3456789' and len(d) in (15, 16)


def brn(s):
    d = digits(s)
    if len(d) != 10:
        return False
    w = (1, 3, 7, 1, 3, 7, 1, 3, 5)
    t = sum(int(a) * b for a, b in zip(d[:9], w)) + int(d[8]) * 5 // 10
    return (10 - t % 10) % 10 == int(d[9])


def brn_personal(s):
    """A business registration number of a person (middle digits 01-79 and 90-99); 80-89 are corporations, which are public."""
    d = digits(s)
    return brn(d) and not 80 <= int(d[3:5]) <= 89


def crn(s):
    d = digits(s)
    if len(d) != 13:
        return False
    t = sum(int(a) * (1 if i % 2 == 0 else 2) for i, a in enumerate(d[:12]))
    return (10 - t % 10) % 10 == int(d[12])


DRIVING_REGION = {'11': '서울', '12': '부산', '13': '경기남부', '14': '강원', '15': '충북', '16': '충남', '17': '전북', '18': '전남',
                  '19': '경북', '20': '경남', '21': '제주', '22': '대구', '23': '인천', '24': '광주', '25': '대전', '26': '울산',
                  '28': '경기북부'}


def driving(s):
    d = digits(s)
    return len(d) == 12 and d[:2] in DRIVING_REGION


def ipv4(s):
    p = s.split('.')
    return len(p) == 4 and all(x.isdigit() and 0 <= int(x) <= 255 and (x == '0' or not x.startswith('0')) for x in p) and p[0] != '0'


def date_any(s):
    """A calendar date in one of the written forms (2020.1.5, 2020-01-05, 2020년 1월 5일, 20200105, 200105)."""
    return parse_date(s) is not None


def parse_date(s):
    m = re.search(r'(\d{4})\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})', s) or re.fullmatch(r'\s*(\d{4})(\d{2})(\d{2})\s*', s)
    if not m:
        m6 = re.fullmatch(r'\s*(\d{2})(\d{2})(\d{2})\s*', s)
        if not m6:
            return None
        yy = int(m6.group(1))
        y = 2000 + yy if yy <= 26 else 1900 + yy
        m = (y, int(m6.group(2)), int(m6.group(3)))
    else:
        m = tuple(int(x) for x in m.groups())
    try:
        return datetime.date(*m)
    except ValueError:
        return None


CHECKS = {'rrn': rrn, 'frn': frn, 'luhn': luhn, 'card': card, 'brn': brn, 'brn_personal': brn_personal, 'crn': crn, 'driving': driving, 'ipv4': ipv4,
          'date': date_any}


# ---- disclosers -----------------------------------------------------------------------------------------------------
def decade(year):
    return f'{year // 10 * 10}년대'


def d_rrn(s, ctx='', fine=False):
    d = digits(s)
    if len(d) == 7 or (len(d) < 13 and len(d) >= 7):         # a partly hidden number: the date and the sex digit only
        x = rrn_date(d[:7] + '000000')
        if x:
            return {'attrs': [('age', f'{x[0]}년생' if fine else decade(x[0])), ('sex', '남' if x[3] % 2 else '여')], 'status': '일부 표시'}
    x = rrn_date(d)
    if not x:
        return {'attrs': [], 'status': '검증 불가'}
    y, _, _, g = x
    ok = (frn_checksum_ok(d) if g in (5, 6, 7, 8) else rrn_checksum_ok(d))
    return {'attrs': [('age', f'{y}년생' if fine else decade(y)), ('sex', '남' if g % 2 else '여')], 'status': ''}


def d_none(s, ctx='', fine=False):
    return {'attrs': [], 'status': ''}


DISCLOSE = {'rrn': d_rrn, 'none': d_none}        # v1: short tags; a registration number shows age band and sex, nothing else does


def selftest():
    d = '800101123456'
    c = (11 - rrn_sum(d + '0')) % 10
    assert rrn_checksum_ok(d + str(c))
    assert luhn('4539578763621486') and not luhn('4539578763621487')
    assert brn('220-81-62517') and not brn('220-81-62518') and not brn_personal('220-81-62517')
    assert driving('11-21-123456-01') and not driving('99-21-123456-01')
    assert ipv4('192.168.0.1') and not ipv4('256.1.1.1')
    r = d_rrn('8001011234563')
    assert r['attrs'] == [('age', '1980년대'), ('sex', '남')] and r['status'] == ''
    print('VALIDATORS SELFTEST PASS')


if __name__ == '__main__':
    selftest()

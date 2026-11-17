"""Normalize odd or wrong input before detecting (design: "Wrong or odd input that pattern rules miss").

simple(text) -> text                   same meaning, one shape: full-width digits and letters, zero-width and look-alike characters,
                                       decomposed jamo (NFC), Korean numerals and O/l swaps inside long number runs, spaced digits
mapped(text) -> (norm, index map)      the same, 1:1 where possible; map[i] = index in the original of norm[i] (for replacing in place)

Only changes that cannot turn ordinary words into numbers are made: Korean numerals only in a run of 9 or more, O/l swaps only inside
a run of 6 or more digit-like characters that holds at least 4 real digits.
"""
import re
import unicodedata

ZERO = dict.fromkeys(map(ord, '​‌‍⁠﻿­'), None)
KNUM = dict(zip('공영일이삼사오육륙칠팔구', '001234566789'.replace('6', '6', 1)))
KNUM['륙'] = '6'
KNUM_RUN = re.compile('[공영일이삼사오육륙칠팔구][공영일이삼사오육륙칠팔구\\s.\\-]{8,}[공영일이삼사오육륙칠팔구]')
DIGITLIKE = re.compile(r'(?<![A-Za-z가-힣])[0-9OoIl][0-9OoIl\s.\-]{4,}[0-9OoIl](?![A-Za-z가-힣])')
FULL = {ord(c): chr(ord(c) - 0xFEE0) for c in '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'}
FULL.update({0x2010: '-', 0x2011: '-', 0x2012: '-', 0x2013: '-', 0x2014: '-', 0x2212: '-', 0xFF0D: '-', 0x3000: ' ', 0xFF0E: '.',
             0xFF1A: ':', 0xFF0F: '/', 0xFF08: '(', 0xFF09: ')', 0xFF0B: '+', 0xFF0C: ','})


def _runs(text):
    def digits(m):
        s = m.group(0)
        d = s.translate({ord('O'): '0', ord('o'): '0', ord('I'): '1', ord('l'): '1'})
        return d if sum(c.isdigit() for c in s) >= 4 else s

    def korean(m):
        return ''.join(KNUM.get(c, c) for c in m.group(0))
    text = KNUM_RUN.sub(korean, text)
    return DIGITLIKE.sub(digits, text)


def simple(text):
    if not text:
        return text
    t = unicodedata.normalize('NFC', text.translate(ZERO)).translate(FULL)
    return _runs(t)


def mapped(text):
    """(norm, map). Characters that disappear (zero width) are skipped, so len(norm) <= len(text)."""
    out, idx = [], []
    for i, c in enumerate(text):
        if ord(c) in ZERO:
            continue
        c2 = c.translate(FULL)
        out.append(c2)
        idx.append(i)
    t = ''.join(out)
    t2 = _runs(t)                                   # runs change characters 1:1, so the map stays valid
    assert len(t2) == len(t)
    return t2, idx


def selftest():
    assert simple('８５０３１２－１２３４５６５') == '850312-1234565'
    assert simple('85​0312-1234565') == '850312-1234565'
    assert simple('일이삼사오육칠팔구영일이삼') == '1234567890123'
    assert simple('이사 오육 구') == '이사 오육 구'                      # ordinary words stay words
    assert simple('O1O-l234-5678') == '010-1234-5678'
    assert simple('한글') == '한글'
    n, m = mapped('85​0312')
    assert n == '850312' and m == [0, 1, 3, 4, 5, 6]
    print('NORMALIZE SELFTEST PASS')


if __name__ == '__main__':
    selftest()

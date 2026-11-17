"""`hd form list <in.hwpx>` and `hd form fill <in.hwpx> <out.hwpx> --set name=value [--set ...]`."""
import sys

from . import forms


def main(args):
    if len(args) >= 2 and args[0] == 'list':
        for part, kind, a in forms.listing(args[1]):
            print('FORM', kind, repr(a.get('name', '')), repr(a.get('caption', '')),
                  a.get('value') or a.get('selectedValue') or '', a.get('radioGroupName', ''))
        return 0
    if len(args) >= 3 and args[0] == 'fill':
        values, rest = {}, args[3:]
        while rest:
            if rest[0] != '--set' or len(rest) < 2 or '=' not in rest[1]:
                break
            k, v = rest[1].split('=', 1)
            values[k], rest = v, rest[2:]
        if rest or not values:
            print('usage: hd form fill <in.hwpx> <out.hwpx> --set name=value [--set ...]')
            return 2
        missing = forms.fill_file(args[1], args[2], values)
        for k in missing:
            print('FORM MISSING', k)
        print('FORM FILLED', len(values) - len(missing), 'of', len(values), '->', args[2])
        return 1 if missing else 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
RFC 8785 (JCS) canonical JSON serialization + SHA-256, stdlib only.

Why not `json.dumps(sort_keys=True, separators=(",", ":"))`:

  * `sort_keys` orders by Unicode code point; RFC 8785 orders by UTF-16 code units, which
    differs for keys containing characters above U+FFFF (astral plane vs. BMP).
  * the default `ensure_ascii=True` escapes non-ASCII; RFC 8785 requires literal UTF-8.
  * Python `repr(float)` is shortest-round-trip but switches to exponent notation on different
    bounds than ECMAScript `Number::toString` (`1e-07` vs `1e-7`, and never `1e+21`), so the
    digits and the exponent marker both have to be re-derived from the ECMAScript algorithm.

I-JSON constraints are enforced: no NaN/Infinity, no duplicate keys, no lone surrogates,
integers inside the safe double range.
"""
import hashlib
import math


class CanonicalError(ValueError):
    pass


def _num(v):
    """ECMAScript Number::toString, per RFC 8785 section 2 / ES 2018 7.1.12.7."""
    if isinstance(v, bool):
        raise CanonicalError("boolean is not a number")
    if isinstance(v, int):
        if abs(v) >= 2 ** 53:
            raise CanonicalError(f"integer {v} is outside the I-JSON safe range")
        return str(v)
    if not isinstance(v, float):
        raise CanonicalError(f"not a number: {v!r}")
    if math.isnan(v) or math.isinf(v):
        raise CanonicalError("NaN/Infinity are not representable in I-JSON")
    if v == 0:
        return "0"                      # -0.0 canonicalizes to "0"
    sign = "-" if v < 0 else ""
    a = abs(v)
    s = repr(a)                         # shortest string that round-trips
    if "e" in s or "E" in s:
        mant, _, exp = s.lower().partition("e")
        e10 = int(exp)
    else:
        mant, e10 = s, 0
    ip, _, fp = mant.partition(".")
    digits_all = ip + fp
    leading_zeros = len(digits_all) - len(digits_all.lstrip("0"))
    digits = digits_all.lstrip("0").rstrip("0") or "0"
    n = len(ip) - leading_zeros + e10    # a = 0.digits x 10**n
    k = len(digits)
    if -6 < n <= 21:
        if n <= 0:
            out = "0." + "0" * (-n) + digits
        elif n >= k:
            out = digits + "0" * (n - k)
        else:
            out = digits[:n] + "." + digits[n:]
    else:
        exp_val = n - 1
        mant_s = digits[0] + ("." + digits[1:] if k > 1 else "")
        out = f"{mant_s}e{'+' if exp_val >= 0 else '-'}{abs(exp_val)}"
    return sign + out


def _utf16_units(s):
    units = []
    for ch in s:
        o = ord(ch)
        if o < 0x10000:
            units.append(o)
        else:
            o -= 0x10000
            units.extend((0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)))
    return units


_ESCAPES = {"\u0008": "\\b", "\u000c": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t",
            '"': '\\"', "\\": "\\\\"}


def _esc(s):
    out = []
    for ch in s:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            raise CanonicalError("lone surrogate is not representable in I-JSON")
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif cp < 0x20:
            out.append("\\u%04x" % cp)
        else:
            out.append(ch)           # non-ASCII stays literal UTF-8
    return '"' + "".join(out) + '"'


def dumps(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _num(value)
    if isinstance(value, str):
        return _esc(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(dumps(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = list(value.keys())
        for key in keys:
            if not isinstance(key, str):
                raise CanonicalError(f"non-string object key {key!r}")
        if len(set(keys)) != len(keys):
            raise CanonicalError("duplicate object keys")
        ordered = sorted(keys, key=_utf16_units)
        return "{" + ",".join(_esc(key) + ":" + dumps(value[key]) for key in ordered) + "}"
    raise CanonicalError(f"unsupported type {type(value).__name__}")


def canonical_bytes(value):
    return dumps(value).encode("utf-8")


def canonical_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

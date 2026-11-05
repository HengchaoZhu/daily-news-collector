from newscollector.normalize import canonical_url, normalize_title, title_fingerprint, url_fingerprint


def test_canonical_url_strips_tracking_and_normalizes_host():
    a = "https://www.Example.com/story/?utm_source=x&id=1&fbclid=abc#top"
    b = "https://example.com/story?id=1"
    assert canonical_url(a) == b
    assert url_fingerprint(a) == url_fingerprint(b)


def test_canonical_url_keeps_meaningful_query_sorted():
    assert canonical_url("https://a.com/p?b=2&a=1") == "https://a.com/p?a=1&b=2"


def test_title_fingerprint_ignores_case_punctuation_and_html():
    assert normalize_title("Fed &amp; <b>Markets</b>: Rates HOLD!") == "fed markets rates hold"
    assert title_fingerprint("Fed & Markets: rates hold") == title_fingerprint("FED  MARKETS RATES HOLD")

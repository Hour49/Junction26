#!/usr/bin/env python3
"""Query public, no-login JSON sources for /pain-points and print compact results.

Stdlib only. Run from the project root:
  python3 .claude/skills/pain-points/fetch_public.py <source> "<query>" [options]

Sources:
  hn        Hacker News comments/stories (Algolia)          --tags comment|story
  se        Stack Exchange questions                       --site money|cooking|...
  gh        GitHub issues
  appsearch App Store app search (find the app id)          --country fi|se|gb|us
  appreviews App Store reviews RSS; query = app id          --country fi|se|gb|us --maxstars 3 --page 1..10
  openalex  OpenAlex works
  crossref  Crossref works
  pubmed    PubMed (esearch + esummary)
  openfda   openFDA drug adverse events; query = openFDA search expression
  cfpb      CFPB consumer complaints (403 to this helper on 2026-11-10; use WebFetch)
  wiki      Wikipedia search                               --lang en|fi
  suomi24   Suomi24 forum search, most relevant first; put exact phrases in "double quotes"
  page      any public page as plain text; query = URL     --grep <word> for verbatim context
Output: one block per hit with the fields needed to cite it (URL, date, text).
Errors (403, 429, timeout) are printed as "blocked: <url> (<reason>)" and exit code 2.
"""
import argparse, gzip, html, json, re, sys, time, urllib.error, urllib.parse, urllib.request

UA = "junction-pitch-research/1.0 (hackathon research script; polite, low volume)"


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
    except urllib.error.HTTPError as e:
        print(f"blocked: {url} (HTTP {e.code})")
        sys.exit(2)
    except Exception as e:  # timeout, DNS, TLS
        print(f"blocked: {url} ({type(e).__name__}: {e})")
        sys.exit(2)
    text = data.decode("utf-8", "replace")
    return text if raw else json.loads(text)


def clean(s, n):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n] + " …[cut]"


def out(**kw):
    print("\n".join(f"{k}: {v}" for k, v in kw.items() if v not in (None, "")))
    print("---")


def q(s):
    return urllib.parse.quote(s)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source")
    p.add_argument("query")
    p.add_argument("--n", type=int, default=10, help="max results (default 10)")
    p.add_argument("--tags", default="comment")
    p.add_argument("--site", default="money")
    p.add_argument("--country", default="fi")
    p.add_argument("--lang", default="en")
    p.add_argument("--maxstars", type=int, default=5, help="appreviews: keep reviews with at most this many stars")
    p.add_argument("--page", type=int, default=1, help="appreviews: RSS page 1-10 (50 reviews each)")
    p.add_argument("--grep", default="", help="page: keyword to show context around")
    p.add_argument("--chars", type=int, default=600, help="max text chars per hit")
    a = p.parse_args()
    s, n, c = a.source, a.n, a.chars

    if s == "hn":
        d = get(f"https://hn.algolia.com/api/v1/search?query={q(a.query)}&tags={a.tags}&hitsPerPage={n}")
        for h in d["hits"]:
            out(url=f"https://news.ycombinator.com/item?id={h['objectID']}", date=h.get("created_at", "")[:10],
                points=h.get("points"), title=h.get("title") or h.get("story_title"),
                text=clean(h.get("comment_text") or h.get("story_text") or "", c))
    elif s == "se":
        d = get(f"https://api.stackexchange.com/2.3/search/advanced?q={q(a.query)}&site={a.site}"
                f"&order=desc&sort=relevance&filter=withbody&pagesize={n}")
        for h in d.get("items", []):
            out(url=h["link"], date=time.strftime("%Y-%m-%d", time.gmtime(h["creation_date"])),
                score=h.get("score"), answers=h.get("answer_count"), title=clean(h["title"], 200),
                text=clean(h.get("body", ""), c))
    elif s == "gh":
        d = get(f"https://api.github.com/search/issues?q={q(a.query)}&per_page={n}")
        for h in d.get("items", []):
            out(url=h["html_url"], date=h["created_at"][:10], comments=h.get("comments"),
                title=h["title"], text=clean(h.get("body") or "", c))
    elif s == "appsearch":
        d = get(f"https://itunes.apple.com/search?term={q(a.query)}&country={a.country}&entity=software&limit={n}")
        for h in d.get("results", []):
            out(id=h["trackId"], name=h["trackName"], seller=h.get("sellerName"),
                rating=h.get("averageUserRating"), ratings=h.get("userRatingCount"), url=h.get("trackViewUrl"))
    elif s == "appreviews":
        url = (f"https://itunes.apple.com/{a.country}/rss/customerreviews/page={a.page}/id={q(a.query)}"
               f"/sortBy=mostRecent/json")
        entries = get(url).get("feed", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        print(f"feed: {url}\nlink for citations: https://apps.apple.com/{a.country}/app/id{a.query}?see-all=reviews\n---")
        for h in [e for e in entries if "im:rating" in e and int(e["im:rating"]["label"]) <= a.maxstars][:n]:
            out(stars=h["im:rating"]["label"], date=h.get("updated", {}).get("label", "")[:10],
                version=h.get("im:version", {}).get("label"), title=h["title"]["label"],
                text=clean(h["content"]["label"], c), review_url=h.get("id", {}).get("label"))
    elif s == "openalex":
        d = get(f"https://api.openalex.org/works?search={q(a.query)}&per-page={n}&sort=relevance_score:desc")
        for h in d.get("results", []):
            ab = h.get("abstract_inverted_index") or {}
            words = sorted((i, w) for w, idx in ab.items() for i in idx)
            out(url=h.get("doi") or h["id"], year=h.get("publication_year"), cited=h.get("cited_by_count"),
                title=h.get("display_name"), venue=((h.get("primary_location") or {}).get("source") or {}).get("display_name"),
                abstract=clean(" ".join(w for _, w in words), c))
    elif s == "crossref":
        d = get(f"https://api.crossref.org/works?query={q(a.query)}&rows={n}")
        for h in d["message"]["items"]:
            dp = (h.get("issued", {}).get("date-parts") or [[None]])[0]
            out(url=h.get("URL"), year=dp[0], title=" ".join(h.get("title") or []),
                venue=" ".join(h.get("container-title") or []), abstract=clean(h.get("abstract", ""), c))
    elif s == "pubmed":
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        ids = get(f"{base}/esearch.fcgi?db=pubmed&retmode=json&retmax={n}&term={q(a.query)}")["esearchresult"]["idlist"]
        if ids:
            d = get(f"{base}/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}")["result"]
            for i in ids:
                h = d[i]
                out(url=f"https://pubmed.ncbi.nlm.nih.gov/{i}/", date=h.get("pubdate"), title=h.get("title"),
                    venue=h.get("source"))
    elif s == "openfda":
        d = get(f"https://api.fda.gov/drug/event.json?search={q(a.query)}&limit={n}")
        print(f"total matching reports: {d.get('meta', {}).get('results', {}).get('total')}\n---")
        for h in d.get("results", []):
            out(report=h.get("safetyreportid"), date=h.get("receivedate"),
                reactions=", ".join(r.get("reactionmeddrapt", "") for r in h.get("patient", {}).get("reaction", [])))
    elif s == "cfpb":
        d = get("https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
                f"?search_term={q(a.query)}&size={n}&has_narrative=true")
        print(f"total: {d.get('hits', {}).get('total')}\n---")
        for h in d.get("hits", {}).get("hits", []):
            x = h["_source"]
            out(id=x.get("complaint_id"), date=(x.get("date_received") or "")[:10], product=x.get("product"),
                company=x.get("company"), text=clean(x.get("complaint_what_happened", ""), c),
                url=f"https://www.consumerfinance.gov/data-research/consumer-complaints/search/detail/{x.get('complaint_id')}")
    elif s == "wiki":
        d = get(f"https://{a.lang}.wikipedia.org/w/api.php?action=query&list=search&format=json"
                f"&srlimit={n}&srsearch={q(a.query)}")
        for h in d["query"]["search"]:
            out(url=f"https://{a.lang}.wikipedia.org/wiki/{q(h['title'].replace(' ', '_'))}",
                title=h["title"], text=clean(h["snippet"], c))
    elif s == "suomi24":
        url = f"https://keskustelu.suomi24.fi/haku?keyword={q(a.query)}&jarjestys=osuvimmat"
        page = get(url, raw=True)
        total = re.search(r'search-page__summary[^>]*><strong>(.*?)</strong>', page)
        print(f"search: {url}\nthreads found: {clean(total.group(1), 40) if total else '?'}\n---")
        cards = re.findall(r'<article class="thread-card".*?</article>', page, re.S)
        for card in cards[:n]:
            href = re.search(r'href="(/t/\d+/[^"]*)"[^>]*data-list-link>(.*?)</a>', card, re.S)
            body = re.search(r'thread-card__body">(.*?)</div>', card, re.S)
            date = re.search(r'datetime="([\d-]{10})', card)
            replies = re.search(r'aria-label="(\d+) vastaus', card)
            if href:
                out(url="https://keskustelu.suomi24.fi" + href.group(1), date=date and date.group(1),
                    replies=replies and replies.group(1), title=clean(href.group(2), 200),
                    text=clean(body.group(1) if body else "", c))
        if not cards:
            print("no threads parsed; open the search page with WebFetch instead")
    elif s == "page":  # query = URL; --grep word prints text around each match (verbatim quotes)
        page = get(a.query, raw=True)
        page = re.sub(r"<(script|style|noscript|svg)\b.*?</\1>", " ", page, flags=re.S | re.I)
        text = clean(re.sub(r"<(br|/p|/div|/li|/h\d|/article)[^>]*>", "\n", page, flags=re.I), 10**7)
        print(f"url: {a.query}\n---")
        if not a.grep:
            print(text[:c * n])
        for m in list(re.finditer(re.escape(a.grep), text, re.I))[:n] if a.grep else []:
            out(match=text[max(0, m.start() - c // 2):m.end() + c // 2])
    else:
        p.error(f"unknown source {s}")


if __name__ == "__main__":
    main()

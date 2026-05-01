import asyncio
import httpx
import psycopg2
from datetime import datetime, timedelta, timezone
from app.celery_app import celery_app
from app.services.wb_api.token_loader import ensure_token

FREQ_URL = "https://seller-analytics-api.wildberries.ru/api/v2/search-report/product/search-texts"
DB_DSN = "postgresql://bidder:WbBidder2026Secure@localhost:5432/wb_bidder"
PAGE_LIMIT = 30
PAGE_DELAY = 10
MAX_PAGES = 4
WEEK_SEC = 7 * 86400

def _run(coro):
    loop = asyncio.new_event_loop()
    try: return loop.run_until_complete(coro)
    finally: loop.close()

def _g(cur, k, d=''):
    cur.execute("SELECT value FROM app_settings WHERE key=%s", (k,))
    r = cur.fetchone()
    return r[0] if r and r[0] else d

def _s(cur, k, v):
    cur.execute("INSERT INTO app_settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=%s", (k,v,v))

@celery_app.task(name="app.tasks.frequency.load_frequencies")
def load_frequencies():
    print("[FREQ] Task started")
    _run(_load())

async def _load():
    if not await ensure_token():
        print("[FREQ] No token"); return

    conn = psycopg2.connect(DB_DSN); conn.autocommit = True; cur = conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key='wb_api_token'")
    token = cur.fetchone()[0]

    rnm = int(_g(cur,'freq_current_nm','0'))
    roff = int(_g(cur,'freq_page_offset','0'))

    nm_id = 0; cids = []

    if rnm:
        cur.execute("SELECT DISTINCT cl.campaign_id FROM clusters cl JOIN campaigns c ON c.wb_campaign_id=cl.campaign_id WHERE cl.nm_id=%s AND c.status=9", (rnm,))
        cids = [r[0] for r in cur.fetchall()]
        if cids:
            nm_id = rnm
            print(f"[FREQ] Resume nm={nm_id} offset={roff}")
        else:
            _s(cur,'freq_current_nm','0'); _s(cur,'freq_page_offset','0'); roff=0

    if not nm_id:
        roff = 0
        fv = _g(cur,'freq_finished_at','')
        if fv:
            fa = datetime.fromisoformat(fv)
            if datetime.now(timezone.utc) - fa < timedelta(seconds=WEEK_SEC):
                print("[FREQ] Cooldown"); conn.close(); return

        lnm = int(_g(cur,'freq_cursor','0'))
        cur.execute("SELECT DISTINCT cl.nm_id FROM clusters cl JOIN campaigns c ON c.wb_campaign_id=cl.campaign_id WHERE c.status=9 AND cl.nm_id>%s ORDER BY cl.nm_id LIMIT 1", (lnm,))
        row = cur.fetchone()
        if not row:
            _s(cur,'freq_finished_at', datetime.now(timezone.utc).isoformat())
            _s(cur,'freq_cursor','0'); _s(cur,'freq_current_nm','0')
            print("[FREQ] Cycle done"); conn.close(); return

        nm_id = row[0]
        cur.execute("SELECT DISTINCT cl.campaign_id FROM clusters cl JOIN campaigns c ON c.wb_campaign_id=cl.campaign_id WHERE cl.nm_id=%s AND c.status=9", (nm_id,))
        cids = [r[0] for r in cur.fetchall()]
        print(f"[FREQ] New nm={nm_id} campaigns={cids}")

    # Pre-load all norm_queries for this nm_id to check matches
    cur.execute("SELECT DISTINCT norm_query FROM clusters WHERE nm_id=%s AND campaign_id = ANY(%s)", (nm_id, cids))
    known_queries = set(r[0] for r in cur.fetchall())
    print(f"[FREQ] Known queries for nm={nm_id}: {len(known_queries)}")

    # Check how many still need frequency
    cur.execute("SELECT COUNT(*) FROM clusters WHERE nm_id=%s AND campaign_id=ANY(%s) AND frequency=0", (nm_id, cids))
    remaining = cur.fetchone()[0]
    if remaining == 0:
        print(f"[FREQ] All queries for nm={nm_id} already have frequency, skipping")
        _s(cur,'freq_current_nm','0'); _s(cur,'freq_page_offset','0'); _s(cur,'freq_cursor',str(nm_id))
        conn.close(); return

    now = datetime.now(timezone.utc)
    ps = (now - timedelta(days=6)).strftime('%Y-%m-%d')
    pe = now.strftime('%Y-%m-%d')
    hdr = {'Authorization': token, 'Content-Type': 'application/json'}
    all_items = []; off = roff; pg = 0; done = False
    no_match_streak = 0

    async with httpx.AsyncClient(timeout=20) as cl:
        while pg < MAX_PAGES:
            try:
                r = await cl.post(FREQ_URL, headers=hdr, json={
                    "nmIds":[nm_id], "currentPeriod":{"start":ps,"end":pe},
                    "topOrderBy":"openCard", "orderBy":{"field":"openCard","mode":"desc"},
                    "limit":PAGE_LIMIT, "offset":off})
            except Exception as e:
                print(f"[FREQ] HTTP err: {e}"); break

            if r.status_code == 429:
                print(f"[FREQ] 429 at offset={off}, exit")
                _s(cur,'freq_current_nm',str(nm_id)); _s(cur,'freq_page_offset',str(off))
                _upd(cur, all_items, nm_id, cids, known_queries); conn.close(); return

            if r.status_code != 200:
                print(f"[FREQ] {r.status_code}: {r.text[:150]}"); break

            batch = r.json().get('data',{}).get('items',[]) or []
            # Count matches in this batch
            matches = sum(1 for it in batch if it.get('text','').strip() in known_queries)
            all_items.extend(batch); pg += 1
            print(f"[FREQ] offset={off}: {len(batch)} items, {matches} matches (page {pg}/{MAX_PAGES})")

            if len(batch) < PAGE_LIMIT: done = True; break

            # If 3 consecutive pages with 0 matches, stop — rest won't match either
            if matches == 0:
                no_match_streak += 1
                if no_match_streak >= 2:
                    print(f"[FREQ] No matches for {no_match_streak} pages, finishing nm={nm_id}")
                    done = True; break
            else:
                no_match_streak = 0

            off += PAGE_LIMIT
            await asyncio.sleep(PAGE_DELAY)

    u = _upd(cur, all_items, nm_id, cids, known_queries)
    print(f"[FREQ] nm={nm_id}: {len(all_items)} fetched, {u} updated")

    if done:
        _s(cur,'freq_current_nm','0'); _s(cur,'freq_page_offset','0'); _s(cur,'freq_cursor',str(nm_id))
    else:
        _s(cur,'freq_current_nm',str(nm_id)); _s(cur,'freq_page_offset',str(off))
    conn.close()

def _upd(cur, items, nm_id, cids, known):
    u = 0
    for it in items:
        t = it.get('text','').strip()
        if not t or t.isdigit() or t not in known: continue
        f = (it.get('frequency') or {}).get('current',0) or 0
        ap = float((it.get('avgPosition') or {}).get('current',0) or 0)
        if f <= 0: continue
        for cid in cids:
            cur.execute("UPDATE clusters SET frequency=%s,avg_position=%s WHERE campaign_id=%s AND nm_id=%s AND norm_query=%s",(f,ap,cid,nm_id,t))
            u += cur.rowcount
    return u

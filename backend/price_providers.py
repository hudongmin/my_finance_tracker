# price_providers.py  — Alpha + Yahoo 兜底；支持 KRX/SLV；A股走东方财富
import os
import re
import json
import time
import requests

# =============== 环境变量（兼容两种命名） ===============
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHAVANTAGE_API_KEY")

# =============== 中文关键词翻译 ===============
TRANSLATION_MAP = {
    "黄金": "gold",
    "比特币": "bitcoin",
    "白银": "silver",
    "原油": "crude oil",
    "美债": "US Treasury",
    "美国国债": "US Treasury bond",
    "苹果": "Apple",
    "特斯拉": "Tesla",
    "英伟达": "Nvidia",
    "纳斯达克": "NASDAQ",
    "标普500": "S&P 500",
    # 场内/场外基金示例
    "恒指互联": "159202",
    "恒生互联网": "159202",
}

# =============== 统一报价对象 ===============
class QuoteResult:
    def __init__(self, symbol, name=None, price=None, currency=None, ts=None, source=None, exchange=None):
        self.symbol = symbol
        self.name = name
        self.price = price
        self.currency = currency
        self.ts = ts
        self.source = source
        self.exchange = exchange
    def to_json(self):
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": self.price,
            "currency": self.currency,
            "ts": self.ts,
            "source": self.source,
            "exchange": self.exchange
        }

# =============== A股/基金：交易所猜测 & 东方财富接口 ===============
def guess_exchange(code: str):
    """根据代码猜交易所：返回 secid 前缀：'0' 深市, '1' 沪市"""
    if not code or not code.isdigit() or len(code) != 6:
        return None
    # 深圳：0/1/3 开头
    if code[0] in ('0', '1', '3'):
        return '0'  # SZ
    # 上海：5/6 开头
    if code[0] in ('5', '6'):
        return '1'  # SH
    return None

def eastmoney_stock_quote(code: str):
    p = guess_exchange(code)
    if not p:
        return None
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {"secid": f"{p}.{code}", "fields": "f43,f57,f58,f169,f170"}  # f43最新价, f57代码, f58名称
    try:
        r = requests.get(url, params=params, timeout=12, headers={"Referer": "https://quote.eastmoney.com/"})
        j = r.json().get("data") or {}
        if not j:
            return None
        symbol, name, raw_price = j.get("f57") or code, j.get("f58"), j.get("f43")
        price = float(raw_price) if raw_price is not None else None
        return QuoteResult(symbol=symbol, name=name, price=price, currency="CNY", ts=None,
                           source="Eastmoney-Stock", exchange="SZ" if p == '0' else "SH")
    except Exception:
        return None

def eastmoney_fund_quote(fund_code: str):
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
    try:
        r = requests.get(url, timeout=12, headers={"Referer": "https://fund.eastmoney.com/"})
        txt = r.text.strip()
        if not txt.startswith("jsonpgz("):
            return None
        j = json.loads(re.search(r"jsonpgz\((.*)\);?$", txt).group(1))
        raw = j.get("gsz") or j.get("dwjz")
        price = float(raw) if raw not in (None, "", "0") else None  # 不用 0 兜底
        if price is None:
            return None
        name, ts = j.get("name"), j.get("gztime") or j.get("jzrq")
        return QuoteResult(symbol=fund_code, name=name, price=price, currency="CNY", ts=ts, source="Eastmoney")
    except Exception:
        return None

def eastmoney_fund_quote_robust(fund_code: str):
    """抓净值 HTML 兜底"""
    url = f"http://fund.eastmoney.com/f10/jshs_{fund_code}.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, timeout=12, headers=headers)
        r.encoding = 'gb2312'
        match = re.search(r'<td>(\d{4}-\d{2}-\d{2})</td>.*?<td class=\'tor bold\'>(.*?)</td>', r.text, re.S)
        if not match:
            return None
        date_str, price_str = match.group(1), match.group(2)
        price = float(price_str)
        name_match = re.search(r'：<a href=.*?>(.*?)</a>\(', r.text)
        name = name_match.group(1) if name_match else None
        return QuoteResult(symbol=fund_code, name=name, price=price, currency="CNY",
                           ts=date_str, source="Eastmoney-HTML")
    except Exception as e:
        print(f"执行 robust_quote 失败 (代码: {fund_code}): {e}")
        return None

# =============== Alpha Vantage（搜索 & 报价） ===============
def _alpha_symbol_search(search_term: str):
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "SYMBOL_SEARCH", "keywords": search_term, "apikey": ALPHA_KEY},
            timeout=12
        )
        r.raise_for_status()
        response_json = r.json()
        if "Error Message" in response_json:
            print(f"Alpha Vantage API 错误: {response_json['Error Message']}")
            return []
        data = response_json.get("bestMatches", []) or []
        results = []
        for m in data:
            results.append({
                "symbol": m.get("1. symbol"),
                "name": m.get("2. name"),
                "type": m.get("3. type"),
                "region": m.get("4. region"),
                "currency": m.get("8. currency"),
                "matchScore": m.get("9. matchScore"),
                "source": "alpha",
            })
        return results
    except Exception as e:
        print(f"_alpha_symbol_search 失败: {e}")
        return []

def alpha_quote(symbol: str):
    if not ALPHA_KEY:
        return None
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": ALPHA_KEY},
            timeout=12
        )
        r.raise_for_status()
        q = r.json().get("Global Quote", {}) or {}
        price = float(q.get("05. price")) if q.get("05. price") else None
        ts = q.get("07. latest trading day")
        return QuoteResult(symbol=symbol, price=price, currency=None, ts=ts, source="AlphaVantage")
    except Exception as e:
        print(f"alpha_quote 失败: {e}")
        return None

# =============== Yahoo 兜底（搜索 + 多重报价） ===============
_Y_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def yahoo_search(q: str):
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": q, "lang": "en-US", "region": "US"},
            headers=_Y_HEADERS,
            timeout=10
        )
        j = r.json() or {}
        quotes = j.get("quotes") or []
        out = []
        for it in quotes:
            out.append({
                "symbol": it.get("symbol"),
                "name": it.get("shortname") or it.get("longname") or it.get("name"),
                "region": it.get("exchDisp"),
                "currency": it.get("currency"),
                "type": it.get("quoteType"),
                "matchScore": None,
                "source": "yahoo",
            })
        return out
    except Exception as e:
        print("[yahoo_search] error:", e)
        return []

def _yahoo_quote_v7(symbol: str) -> QuoteResult | None:
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            params={"symbols": symbol},
            headers={**_Y_HEADERS, "Referer": f"https://finance.yahoo.com/quote/{symbol}"},
            timeout=10
        )
        j = r.json()
        res = (j.get("quoteResponse") or {}).get("result") or []
        if not res:
            print("[yahoo v7] empty, status=", r.status_code, "body[:200]=", r.text[:200])
            return None
        x = res[0]
        price = x.get("regularMarketPrice")
        if price is None:
            return None
        return QuoteResult(
            symbol=x.get("symbol") or symbol,
            name=x.get("shortName") or x.get("longName"),
            price=float(price),
            currency=x.get("currency"),
            exchange=x.get("fullExchangeName") or x.get("exchange"),
            ts=time.time(),
            source="yahoo",
        )
    except Exception as e:
        print("[yahoo v7] error:", e)
        return None

def _yahoo_quote_chart(symbol: str) -> QuoteResult | None:
    """v8 chart 兜底：从 meta.regularMarketPrice / previousClose 取值"""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": "1d", "interval": "1m"},
            headers={**_Y_HEADERS, "Referer": f"https://finance.yahoo.com/quote/{symbol}"},
            timeout=10
        )
        j = r.json()
        res = (j.get("chart") or {}).get("result") or []
        if not res:
            print("[yahoo v8] empty, status=", r.status_code, "body[:200]=", r.text[:200])
            return None
        meta = res[0].get("meta") or {}
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        if price is None:
            return None
        return QuoteResult(
            symbol=symbol,
            name=None,
            price=float(price),
            currency=meta.get("currency"),
            exchange=meta.get("exchangeName"),
            ts=time.time(),
            source="yahoo-chart",
        )
    except Exception as e:
        print("[yahoo v8] error:", e)
        return None

def _stooq_quote(symbol: str) -> QuoteResult | None:
    """
    Stooq 免费 CSV 兜底（美股/ETF：加 .us；KRX：.ks / .kq）
    SLV -> slv.us
    """
    s = symbol.lower()
    stooq_sym = s
    currency = None
    if "." not in s:
        if s.isalpha():
            stooq_sym = f"{s}.us"; currency = "USD"
        elif s.isdigit() and len(s) == 6:
            stooq_sym = f"{s}.ks"; currency = "KRW"
    else:
        if s.endswith(".us"): currency = "USD"
        if s.endswith(".ks") or s.endswith(".kq"): currency = "KRW"
    url = f"https://stooq.com/q/l/?s={stooq_sym}&i=d"
    try:
        r = requests.get(url, timeout=8)
        text = r.text.strip()
        if r.status_code != 200 or "N/D" in text or text.count("\n") < 1:
            print("[stooq] no data:", r.status_code, text[:120])
            return None
        # CSV: Symbol,Date,Time,Open,High,Low,Close,Volume
        lines = text.splitlines()
        if len(lines) < 2:
            return None
        fields = lines[1].split(",")
        if len(fields) < 7:
            return None
        close = fields[6]
        price = float(close)
        return QuoteResult(symbol=symbol.upper(), name=None, price=price, currency=currency, ts=time.time(), source="stooq", exchange=None)
    except Exception as e:
        print("[stooq] error:", e)
        return None

def yahoo_quote(symbol: str) -> QuoteResult | None:
    s = (symbol or "").strip()
    # 先尝试原符号 v7
    q = _yahoo_quote_v7(s)
    if q and q.price is not None:
        return q
    # 韩国 6位数字：尝试 .KS / .KQ（分别用 v7，再用 v8）
    if s.isdigit() and len(s) == 6:
        for suf in (".KS", ".KQ"):
            q = _yahoo_quote_v7(s + suf) or _yahoo_quote_chart(s + suf)
            if q and q.price is not None:
                return q
    # 再尝试 v8 chart
    q = _yahoo_quote_chart(s)
    if q and q.price is not None:
        return q
    # 最后 Stooq
    return _stooq_quote(s)

# =============== 对外函数（保持你的签名） ===============
def alpha_search(query: str):
    """Alpha 搜索 + Yahoo 兜底；A股六位数直接回填候选"""
    q = (query or "").strip()
    # 翻译字典优先（如 159202）
    mapped_code = TRANSLATION_MAP.get(q)
    if mapped_code and mapped_code.isdigit():
        q = mapped_code

    # 六位数字：直接返回 A股/基金候选
    if q.isdigit() and len(q) == 6:
        cands = []
        ex = guess_exchange(q)
        if ex:
            cands.append({
                "symbol": f"{q}",
                "name": f"场内证券 {q} ({'深' if ex=='0' else '沪'})",
                "type": "ETF/Stock", "region": "CN", "currency": "CNY", "matchScore": "1.0", "source": "eastmoney"
            })
        cands.append({
            "symbol": q, "name": "场外公募基金（猜测）",
            "type": "Fund", "region": "CN", "currency": "CNY", "matchScore": "0.9", "source": "eastmoney"
        })
        return cands

    search_term = TRANSLATION_MAP.get(q, q)
    print(f"原始查询: '{q}', 发送给API的搜索词: '{search_term}'")

    results = []
    if ALPHA_KEY:
        results = _alpha_symbol_search(search_term)

    # Alpha 没 key / 失败 / 返回空 —— 用 Yahoo 兜底（支持 KRX/SLV）
    if not results:
        y = yahoo_search(search_term)
        # 去重合并（以 symbol 为键）
        seen = set()
        out = []
        for item in (results + y):
            sym = item.get("symbol")
            if sym and sym not in seen:
                out.append(item)
                seen.add(sym)
        results = out

    return results

def smart_quote(symbol_or_code: str):
    """
    A股/基金：东方财富；否则 Alpha -> Yahoo (v7->v8->Stooq) 兜底。
    只有 000001.SZ / 600000.SH 这类才按 A 股处理；'005930.KS' 不再误判为 A 股。
    """
    s = (symbol_or_code or "").strip()

    # 1) 纯 6 位数字：优先视为 A 股/ETF
    if s.isdigit() and len(s) == 6:
        q_stock = eastmoney_stock_quote(s)
        if q_stock and q_stock.price is not None:
            return q_stock
        q_realtime = eastmoney_fund_quote(s)
        if q_realtime and q_realtime.price is not None:
            return q_realtime
        q_robust = eastmoney_fund_quote_robust(s)
        if q_robust and q_robust.price is not None:
            return q_robust
        return q_stock or q_realtime or q_robust

    # 2) 形如 000001.SZ / 600000.SH 才视为 A 股；其它后缀不走东方财富
    if '.' in s:
        prefix, suffix = s.split('.', 1)
        suffix = suffix.upper()
        if prefix.isdigit() and len(prefix) == 6 and suffix in {'SZ', 'SH'}:
            return eastmoney_stock_quote(prefix)

    # 3) 非 A 股：Alpha -> Yahoo 多重兜底
    q = alpha_quote(s) if ALPHA_KEY else None
    if q and q.price is not None:
        return q
    return yahoo_quote(s)

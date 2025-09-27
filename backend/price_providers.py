import os
import requests
import json
import re

# 这行代码会从 .env 文件或系统环境变量中加载密钥
ALPHA_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# --- 新增/修改：中文关键词到英文/代码的翻译字典 ---
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
    "恒指互联": "159202",      # <--- 新增：让中文名可以直接映射到代码
    "恒生互联网": "159202"    # <--- 新增：别名
}

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

def alpha_search(query: str):
    q = (query or "").strip()
    
    # --- 核心修改：先在翻译字典里查找，如果找到代码直接返回候选 ---
    mapped_code = TRANSLATION_MAP.get(q)
    if mapped_code and mapped_code.isdigit():
        q = mapped_code

    if q.isdigit() and len(q) == 6:
        cands = []
        ex = guess_exchange(q)
        if ex:
            cands.append({
                "symbol": f"{q}", # 直接返回代码，让 pickSearch 填充
                "name": f"场内证券 {q} ({'深' if ex=='0' else '沪'})",
                "type": "ETF/Stock", "region": "CN", "currency": "CNY", "matchScore": "1.0"
            })
        # 也可以保留对场外基金的猜测
        cands.append({
            "symbol": q, "name": "场外公募基金（猜测）",
            "type": "Fund", "region": "CN", "currency": "CNY", "matchScore": "0.9"
        })
        return cands

    search_term = TRANSLATION_MAP.get(q, q)
    print(f"原始查询: '{q}', 发送给API的搜索词: '{search_term}'")
    if not ALPHA_KEY:
        print("错误: ALPHAVANTAGE_API_KEY 未设置！")
        return []
    try:
        r = requests.get("https://www.alphavantage.co/query", params={
            "function": "SYMBOL_SEARCH", "keywords": search_term, "apikey": ALPHA_KEY
        }, timeout=12)
        r.raise_for_status()
        response_json = r.json()
        if "Error Message" in response_json:
            print(f"Alpha Vantage API 错误: {response_json['Error Message']}")
            return []
        data = response_json.get("bestMatches", []) or []
        results = []
        for m in data:
            results.append({
                "symbol": m.get("1. symbol"), "name": m.get("2. name"),
                "type": m.get("3. type"), "region": m.get("4. region"),
                "currency": m.get("8. currency"), "matchScore": m.get("9. matchScore")
            })
        return results
    except Exception as e:
        print(f"alpha_search 失败: {e}")
        return []

# --- 核心修正：扩展深圳市场的代码识别范围 ---
def guess_exchange(code: str):
    """根据代码猜交易所（修正版）：返回 secid 前缀：'0' 深市, '1' 沪市"""
    if not code or not code.isdigit() or len(code) != 6:
        return None
    # 深圳：0开头(主板), 3开头(创业板), 1开头(ETF等)
    if code[0] in ('0', '3', '1'):
        return '0'  # SZ
    # 上海：6开头(主板), 5开头(基金等)
    if code[0] in ('6', '5'):
        return '1'  # SH
    return None

# --- 新增：一个更稳健的、从HTML页面抓取净值的函数 (用于场外基金) ---
def eastmoney_fund_quote_robust(fund_code: str):
    url = f"http://fund.eastmoney.com/f10/jshs_{fund_code}.html"
    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        r = requests.get(url, timeout=12, headers=headers)
        r.encoding = 'gb2312'
        match = re.search(r'<td>(\d{4}-\d{2}-\d{2})</td>.*?<td class=\'tor bold\'>(.*?)</td>', r.text, re.S)
        if not match: return None
        date_str, price_str = match.group(1), match.group(2)
        price = float(price_str)
        name_match = re.search(r'：<a href=.*?>(.*?)</a>\(', r.text)
        name = name_match.group(1) if name_match else None
        return QuoteResult(symbol=fund_code, name=name, price=price, currency="CNY", ts=date_str, source="Eastmoney-HTML")
    except Exception as e:
        print(f"执行 robust_quote 失败 (代码: {fund_code}): {e}")
        return None

# --- 东方财富 场内基金/股票 实时接口 ---
def eastmoney_stock_quote(code: str):
    p = guess_exchange(code)
    if not p:
        return None
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {"secid": f"{p}.{code}", "fields": "f43,f57,f58,f169,f170"} # f43最新价, f57代码, f58名称
    try:
        r = requests.get(url, params=params, timeout=12, headers={"Referer": "https://quote.eastmoney.com/"})
        j = r.json().get("data") or {}
        if not j: return None
        symbol, name, raw_price = j.get("f57") or code, j.get("f58"), j.get("f43")
        price = float(raw_price) if raw_price is not None else None
        return QuoteResult(symbol=symbol, name=name, price=price, currency="CNY", ts=None, source="Eastmoney-Stock", exchange="SZ" if p=='0' else "SH")
    except Exception:
        return None

# --- 东方财富 场外基金 估值接口 ---
def eastmoney_fund_quote(fund_code: str):
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
    try:
        r = requests.get(url, timeout=12, headers={"Referer": "https://fund.eastmoney.com/"})
        txt = r.text.strip()
        if not txt.startswith("jsonpgz("): return None
        j = json.loads(re.search(r"jsonpgz\((.*)\);?$", txt).group(1))
        price = float(j.get("gsz") or j.get("dwjz") or 0)
        name, ts = j.get("name"), j.get("gztime") or j.get("jzrq")
        return QuoteResult(symbol=fund_code, name=name, price=price, currency="CNY", ts=ts, source="Eastmoney")
    except Exception:
        return None

# --- 智能路由函数 (已更新) ---
def smart_quote(symbol_or_code: str):
    s = (symbol_or_code or "").strip()
    if s.isdigit() and len(s) == 6:
        # 优先作为场内证券（股票/ETF）查询，因为这最快最准
        q_stock = eastmoney_stock_quote(s)
        if q_stock and q_stock.price is not None:
            return q_stock
        
        # 如果不是场内证券，再尝试作为场外基金
        q_realtime = eastmoney_fund_quote(s)
        if q_realtime and q_realtime.price is not None:
            return q_realtime
        
        q_robust = eastmoney_fund_quote_robust(s)
        if q_robust and q_robust.price is not None:
            return q_robust

        # 如果都失败，返回第一个获取到的结果
        return q_stock or q_realtime or q_robust

    if '.' in s and len(s.split('.', 1)[0]) == 6 and s.split('.',1)[0].isdigit():
        return eastmoney_stock_quote(s.split('.',1)[0])

    # 默认走 Alpha Vantage
    return alpha_quote(s)
    
def alpha_quote(symbol: str):
    if not ALPHA_KEY: return None
    try:
        r = requests.get("https://www.alphavantage.co/query", params={
            "function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": ALPHA_KEY
        }, timeout=12)
        r.raise_for_status()
        q = r.json().get("Global Quote", {}) or {}
        price = float(q.get("05. price")) if q.get("05. price") else None
        ts = q.get("07. latest trading day")
        return QuoteResult(symbol=symbol, price=price, currency=None, ts=ts, source="AlphaVantage")
    except Exception as e:
        print(f"alpha_quote 失败: {e}")
        return None
# ====== 我的家庭财务中心 · 后端最小可用版 ======
import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# ---------------- 基础初始化 ----------------
app = Flask(__name__)
# 上线后建议把 * 换成你的 Netlify 域名，如 {"origins": ["https://你的站点.netlify.app"]}
CORS(app, resources={r"/*": {"origins": "*"}})

# SQLite 放在 backend/data.sqlite
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, "data.sqlite")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------- 健康检查 ----------------
@app.get("/health")
def health():
    return jsonify({"ok": True})


# ---------------- 数据模型 ----------------
class BudgetRule(db.Model):
    __tablename__ = "budget_rules"
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)            # 收入 / 支出
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)               # 每月金额（起始月的名义值）
    start_date = db.Column(db.DateTime, nullable=False)        # 用每月1日表示
    end_date = db.Column(db.DateTime, nullable=True)           # 含当月
    growth_rate = db.Column(db.Float, nullable=True, default=0)
    note = db.Column(db.String(200), nullable=True)

    def to_json(self):
        fmt = lambda d: d.strftime('%Y-%m') if d else None
        return {
            "id": self.id,
            "type": self.type,
            "category": self.category,
            "amount": float(self.amount),
            "start_month": fmt(self.start_date),
            "end_month": fmt(self.end_date),
            "growth_rate": float(self.growth_rate or 0),
            "note": self.note or ""
        }


class BudgetEntry(db.Model):
    """收支明细（供预算页面展示/统计）"""
    __tablename__ = "budget_entries"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.String(10), nullable=False)            # 收入 / 支出
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(200), nullable=True)

    def to_json(self):
        return {
            "id": self.id,
            "date": self.date.strftime("%Y-%m-%d"),
            "type": self.type,
            "category": self.category,
            "amount": float(self.amount),
            "note": self.note or ""
        }


class Asset(db.Model):
    """最小可用资产表，适配前端字段"""
    __tablename__ = "assets"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=True)             # 股票/基金/现金/房产/其他
    asset_style = db.Column(db.String(20), nullable=True, default='manual')  # manual/market/fixed
    symbol = db.Column(db.String(50), nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    total_cost = db.Column(db.Float, nullable=False, default=0.0)
    current_value = db.Column(db.Float, nullable=False, default=0.0)
    # 固收相关（可空）
    rate = db.Column(db.Float, nullable=True)
    compounding = db.Column(db.String(20), nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    contribution = db.Column(db.Float, nullable=True)
    contribution_freq = db.Column(db.String(20), nullable=True)

    def to_json(self):
        profit = float(self.current_value) - float(self.total_cost)
        profit_rate = (profit / self.total_cost * 100.0) if self.total_cost else 0.0
        fmt = lambda d: (d.strftime('%Y-%m-%d') if d else None)
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "asset_style": self.asset_style,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "total_cost": float(self.total_cost),
            "current_value": float(self.current_value),
            "profit": profit,
            "profit_rate": profit_rate,
            "rate": self.rate,
            "compounding": self.compounding,
            "start_date": fmt(self.start_date),
            "end_date": fmt(self.end_date),
            "contribution": self.contribution,
            "contribution_freq": self.contribution_freq,
            "transactions": []   # 前端会读取该字段，这里返回空列表避免报错
        }


class Snapshot(db.Model):
    __tablename__ = "snapshots"
    id = db.Column(db.Integer, primary_key=True)
    total_value = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_json(self):
        return {
            "id": self.id,
            "total_value": float(self.total_value),
            "created_at": self.created_at.strftime('%Y-%m-%d')
        }


# ---------------- 辅助函数 ----------------
def compute_total_value() -> float:
    """资产现值合计（无资产表时返回 0）"""
    try:
        total = db.session.query(func.coalesce(func.sum(Asset.current_value), 0.0)).scalar()
        return float(total or 0.0)
    except Exception:
        return 0.0


def parse_date(s: str) -> datetime:
    # 接收 'YYYY-MM-DD'
    return datetime.strptime(s, "%Y-%m-%d")


def parse_month(s: str):
    # 'YYYY-MM' -> (year, month)
    y, m = s.split('-')
    return int(y), int(m)


def ym_to_dt(y: int, m: int):
    return datetime(y, m, 1)


def months_between(a: datetime, b: datetime) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def in_month_window(rule: BudgetRule, y: int, m: int) -> bool:
    t = ym_to_dt(y, m)
    if t < ym_to_dt(rule.start_date.year, rule.start_date.month):
        return False
    if rule.end_date:
        last = ym_to_dt(rule.end_date.year, rule.end_date.month)
        return t <= last    # 含截止月
    return True


def amount_at_month(rule: BudgetRule, y: int, m: int) -> float:
    base = float(rule.amount)
    g = float(rule.growth_rate or 0.0)
    if g == 0:
        return base
    diff_m = months_between(ym_to_dt(rule.start_date.year, rule.start_date.month), ym_to_dt(y, m))
    # 按年增长率折到月：(1+g)^(diff_m/12)
    return base * pow(1.0 + g, diff_m / 12.0)


def gen_rules_for_month(y: int, m: int):
    rows = []
    for r in BudgetRule.query.all():
        if in_month_window(r, y, m):
            rows.append({
                "date": f"{y:04d}-{m:02d}-01",
                "type": r.type,
                "category": r.category,
                "amount": amount_at_month(r, y, m),
                "note": "自动填充"
            })
    return rows


# ---------------- 规则 CRUD ----------------
@app.route('/api/budget/rules', methods=['GET', 'POST'])
def budget_rules():
    if request.method == 'POST':
        data = request.get_json() or {}
        try:
            y, m = parse_month(data.get('start_month'))
            start_dt = ym_to_dt(y, m)
            end_dt = None
            if data.get('end_month'):
                ey, em = parse_month(data['end_month'])
                end_dt = ym_to_dt(ey, em)
            row = BudgetRule(
                type=data.get('type') or '支出',
                category=data.get('category') or '未分类',
                amount=float(data.get('amount') or 0.0),
                start_date=start_dt,
                end_date=end_dt,
                growth_rate=float(data.get('growth_rate') or 0.0),
                note=(data.get('note') or '').strip() or None
            )
            db.session.add(row)
            db.session.commit()
            return jsonify(row.to_json()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 400
    # GET
    rows = BudgetRule.query.order_by(BudgetRule.start_date.asc(), BudgetRule.id.asc()).all()
    return jsonify([r.to_json() for r in rows])


@app.route('/api/budget/rules/<int:rule_id>', methods=['DELETE'])
def budget_rules_delete(rule_id):
    r = BudgetRule.query.get_or_404(rule_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"message": "deleted"})


# ---------------- 一键填充默认项到明细 ----------------
@app.route('/api/budget/autofill', methods=['POST'])
def budget_autofill():
    """
    请求体：{ "month": "YYYY-MM" }
    动作：生成当月规则条目，并写入 BudgetEntry（当日/同类已存在相同金额且备注'自动填充'的记录会跳过）
    """
    data = request.get_json() or {}
    month = (data.get('month') or '').strip()
    if not month:
        return jsonify({"error": "month required, e.g. 2025-09"}), 400
    y, m = parse_month(month)
    to_create = gen_rules_for_month(y, m)
    created = []

    # 查重范围：当月
    from_date = ym_to_dt(y, m)
    to_date = ym_to_dt(y + (m == 12), 1 if m == 12 else m + 1)

    existing = BudgetEntry.query.filter(
        BudgetEntry.date >= from_date,
        BudgetEntry.date < to_date
    ).all()

    for item in to_create:
        # 是否已有同类同额“自动填充”记录
        dup = next((
            e for e in existing
            if e.type == item['type'] and e.category == item['category']
            and abs(e.amount - float(item['amount'])) < 1e-6
            and (e.note or '') == '自动填充'
        ), None)
        if dup:
            continue
        entry = BudgetEntry(
            date=parse_date(item['date']),
            type=item['type'],
            category=item['category'],
            amount=float(item['amount']),
            note=item['note']
        )
        db.session.add(entry)
        created.append(entry)

    db.session.commit()
    return jsonify([e.to_json() for e in created])


# ---------------- 预算明细 & 汇总 ----------------
@app.route('/api/budget/entries', methods=['GET', 'POST'])
def budget_entries():
    if request.method == 'POST':
        data = request.get_json() or {}
        try:
            row = BudgetEntry(
                date=parse_date((data.get('date') or '').strip()),
                type=data.get('type') or '支出',
                category=data.get('category') or '未分类',
                amount=float(data.get('amount') or 0.0),
                note=(data.get('note') or '').strip() or None
            )
            db.session.add(row)
            db.session.commit()
            return jsonify(row.to_json()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    # GET ?start=YYYY-MM-DD&end=YYYY-MM-DD
    start_s = (request.args.get('start') or '').strip()
    end_s = (request.args.get('end') or '').strip()
    q = BudgetEntry.query
    if start_s:
        q = q.filter(BudgetEntry.date >= parse_date(start_s))
    if end_s:
        q = q.filter(BudgetEntry.date <= parse_date(end_s))
    rows = q.order_by(BudgetEntry.date.asc(), BudgetEntry.id.asc()).all()
    return jsonify([r.to_json() for r in rows])


@app.route('/api/budget/entries/<int:entry_id>', methods=['DELETE'])
def budget_entries_delete(entry_id):
    r = BudgetEntry.query.get_or_404(entry_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({'message': 'deleted'})


@app.route('/api/budget/summary', methods=['GET'])
def budget_summary():
    # ?start=YYYY-MM-DD&end=YYYY-MM-DD
    start_s = (request.args.get('start') or '').strip()
    end_s = (request.args.get('end') or '').strip()
    q = BudgetEntry.query
    if start_s:
        q = q.filter(BudgetEntry.date >= parse_date(start_s))
    if end_s:
        q = q.filter(BudgetEntry.date <= parse_date(end_s))
    rows = q.all()
    income = sum(float(r.amount) for r in rows if r.type == '收入')
    expense = sum(float(r.amount) for r in rows if r.type != '收入')
    return jsonify({'income': income, 'expense': expense})


# ---------------- 资产 ----------------
@app.route('/api/assets', methods=['GET', 'POST'])
def assets_api():
    if request.method == 'POST':
        data = request.get_json() or {}
        a = Asset(
            name=data.get('name') or '未命名资产',
            type=data.get('type') or '其他',
            asset_style=data.get('asset_style') or 'manual',
            symbol=(data.get('symbol') or None),
            quantity=(data.get('quantity') or None),
            total_cost=float(data.get('initial_cost') or 0.0),
            current_value=float(data.get('initial_cost') or 0.0),
            rate=(data.get('rate') or None),
            compounding=(data.get('compounding') or None),
            start_date=(parse_date(data['start_date']) if data.get('start_date') else None),
            end_date=(parse_date(data['end_date']) if data.get('end_date') else None),
            contribution=(data.get('contribution') or None),
            contribution_freq=(data.get('contribution_freq') or None),
        )
        db.session.add(a)
        db.session.commit()
        return jsonify(a.to_json()), 201

    rows = Asset.query.order_by(Asset.id.asc()).all()
    return jsonify([r.to_json() for r in rows])


@app.route('/api/assets/<int:aid>', methods=['DELETE'])
def assets_delete(aid):
    a = Asset.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    return jsonify({'message': 'deleted'})


@app.route('/api/assets/<int:aid>/value', methods=['PUT'])
def assets_update_value(aid):
    a = Asset.query.get_or_404(aid)
    data = request.get_json() or {}
    a.current_value = float(data.get('current_value') or 0.0)
    db.session.commit()
    return jsonify(a.to_json())


@app.route('/api/assets/<int:aid>/transactions', methods=['POST'])
def assets_add_tx(aid):
    """
    最小兼容：买入 -> total_cost 增加；卖出 -> total_cost 减少(不小于0)。
    返回更新后的资产，以满足前端更新视图。
    """
    a = Asset.query.get_or_404(aid)
    data = request.get_json() or {}
    t = (data.get('type') or '买入').strip()
    amt = float(data.get('amount') or 0.0)
    if t == '买入':
        a.total_cost = float(a.total_cost) + amt
    else:
        a.total_cost = max(0.0, float(a.total_cost) - amt)
    db.session.commit()
    return jsonify(a.to_json())


# ---------------- 快照 ----------------
@app.route('/api/snapshots', methods=['GET', 'POST'])
def snapshots_api():
    if request.method == 'POST':
        # 取当前资产总值做快照
        total = compute_total_value()
        s = Snapshot(total_value=total)
        db.session.add(s)
        db.session.commit()
        return jsonify(s.to_json()), 201
    # GET ?limit=500
    lim = int(request.args.get('limit', 500))
    rows = Snapshot.query.order_by(Snapshot.created_at.asc(), Snapshot.id.asc()).limit(lim).all()
    return jsonify([r.to_json() for r in rows])


# ---------------- 市场搜索/行情（桩接口，避免 404） ----------------
@app.route('/api/search')
def market_search():
    # 返回空列表即可；以后可接入真实搜索
    q = (request.args.get('q') or '').strip()
    return jsonify([])


@app.route('/api/quote')
def market_quote():
    # 返回一个 price 字段；以后可接入真实行情
    symbol = (request.args.get('symbol') or '').strip()
    return jsonify({'symbol': symbol, 'price': 0})


# ---------------- 财务规划曲线 ----------------
@app.route('/api/plan/curve', methods=['POST'])
def plan_curve():
    """
    请求体：
      { "years": 30, "annual_return": 0.06, "start_value": (可选，默认=当前总资产) }
    逻辑：
      月化收益 = (1+annual_return)**(1/12) - 1
      财富_{t+1} = 财富_t * (1+月化收益) + 当月净现金流(来自规则：收入-支出)
    """
    data = request.get_json() or {}
    years = int(data.get("years", 30))
    annual_return = float(data.get("annual_return", 0.06))
    start_value = float(data.get("start_value", compute_total_value()))
    months = max(1, years * 12)
    r_m = pow(1.0 + annual_return, 1.0/12.0) - 1.0

    # 从“本月”开始
    now = datetime.utcnow()
    y, m = now.year, now.month

    wealth = start_value
    points = []

    for _ in range(months):
        # 本月现金流
        month_income = 0.0
        month_expense = 0.0
        for r in BudgetRule.query.all():
            if in_month_window(r, y, m):
                amt = amount_at_month(r, y, m)
                if r.type == '收入':
                    month_income += amt
                else:
                    month_expense += amt
        net = month_income - month_expense

        # 月终财富
        wealth = wealth * (1.0 + r_m) + net

        points.append({
            "month": f"{y:04d}-{m:02d}",
            "income": month_income,
            "expense": month_expense,
            "net": net,
            "wealth": wealth
        })

        # 下一个月
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1

    return jsonify({
        "params": {"years": years, "annual_return": annual_return, "start_value": start_value},
        "points": points
    })


# ---------------- 启动前建表 ----------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

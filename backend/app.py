# ==== 新增：固定规则（自动默认）+ 规划曲线 ====
from datetime import datetime, timedelta
from flask_cors import CORS
from flask import jsonify

CORS(app, resources={r"/*": {"eunyoung": "*"}})

# 健康检查路由
@app.get("/health")
def health():
    return jsonify({"ok": True})


# ---------- 数据模型 ----------
class BudgetRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)            # 收入 / 支出
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)               # 每月金额（起始月的名义值）
    start_date = db.Column(db.DateTime, nullable=False)        # 规则生效的起始“月份”（用每月1日来表示）
    end_date = db.Column(db.DateTime, nullable=True)           # 可选截止“月份”（含当月）
    growth_rate = db.Column(db.Float, nullable=True, default=0)# 年增长率，例如 0.03
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

# ---------- 月份工具 ----------
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
        # 含截止月
        last = ym_to_dt(rule.end_date.year, rule.end_date.month)
        return t <= last
    return True

def amount_at_month(rule: BudgetRule, y: int, m: int) -> float:
    base = float(rule.amount)
    g = float(rule.growth_rate or 0.0)
    if g == 0:
        return base
    diff_m = months_between(ym_to_dt(rule.start_date.year, rule.start_date.month), ym_to_dt(y, m))
    # 按年增长率折算到月： (1+g)^(diff_m/12)
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

# ---------- 规则 CRUD ----------
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

# ---------- 一键填充（把当月默认项目落为明细） ----------
@app.route('/api/budget/autofill', methods=['POST'])
def budget_autofill():
    """
    请求体：{ "month": "YYYY-MM" }
    动作：生成当月规则条目，并写入 BudgetEntry（若当日/同类已有“自动填充”相同金额记录，将跳过）
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
    if m == 12:
        to_date = ym_to_dt(y + 1, 1)
    else:
        to_date = ym_to_dt(y, m + 1)

    existing = BudgetEntry.query.filter(
        BudgetEntry.date >= from_date,
        BudgetEntry.date < to_date
    ).all()

    for item in to_create:
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

# ---------- 财务规划曲线 ----------
@app.route('/api/plan/curve', methods=['POST'])
def plan_curve():
    """
    请求体：
      { "years": 30, "annual_return": 0.06, "start_value": (可选，默认=当前总资产) }
    逻辑：
      月化收益 = (1+annual_return)**(1/12) - 1
      财富_{t+1} = 财富_t * (1+月化收益) + 当月净现金流(来自规则：收入-支出)
      养老金：作为一条收入规则，设未来起始月即可
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

    for k in range(months):
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

        # 本月结束时的财富
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

<template>
  <div id="app">
    <header>
      <h1>财富自由</h1>
      <nav class="nav">
        <button :class="{active: currentPage==='home'}" @click="go('home')">主页</button>
        <button :class="{active: currentPage==='wealth'}" @click="go('wealth')">财富增值</button>
        <button :class="{active: currentPage==='budget'}" @click="go('budget')">收支预算</button>
        <button :class="{active: currentPage==='planning'}" @click="go('planning')">财务规划</button>
      </nav>
    </header>

    <!-- 主页 -->
    <section v-if="currentPage==='home'" class="home">
      <div class="hero">
        <h2>欢迎回来 👋</h2>
        <p>在这里管理你的 <strong>资产组合</strong> 与 <strong>收入支出</strong>，并生成长期 <strong>财务规划</strong>。</p>
        <div class="cta">
          <button class="primary" @click="go('wealth')">进入 财富增值</button>
          <button class="secondary" @click="go('budget')">进入 收支预算</button>
          <button class="secondary" @click="go('planning')">进入 财务规划</button>
        </div>
      </div>
      <div class="quick-cards">
        <div class="card">
          <h3>当前总资产</h3>
          <p class="big">¥ {{ (totalCurrentValue || 0).toFixed(2) }}</p>
        </div>
        <div class="card">
          <h3>当月净收支</h3>
          <p class="big" :class="netThisMonth>=0 ? 'buy' : 'sell'">¥ {{ netThisMonth.toFixed(2) }}</p>
        </div>
      </div>
    </section>

    <!-- 财富增值（完整） -->
    <section v-if="currentPage==='wealth'" class="page">
      <div class="column">
        <!-- 添加资产的表单 -->
        <div class="form-container">
          <h2>
            添加新资产
            <button class="toggle-btn" @click="runSimulate" v-if="assets.length">组合模拟</button>
          </h2>

          <form @submit.prevent="addAsset">
            <input v-model="newAsset.name" type="text" placeholder="资产名称" required>

            <select v-model="newAsset.type" required>
              <option disabled value="">请选择资产类型</option>
              <option>基金</option>
              <option>股票</option>
              <option>现金</option>
              <option>房产</option>
              <option>其他</option>
            </select>
            
            <!-- 初始成本作为首笔买入（可选） -->
            <input v-model.number="newAsset.initial_cost" type="number" step="0.01" inputmode="decimal" placeholder="初始总成本 (可选)">

            <!-- 资产风格 -->
            <label class="muted">资产风格</label>
            <select v-model="newAsset.asset_style">
              <option value="manual">手动</option>
              <option value="market">市场报价</option>
              <option value="fixed">固定期限/固收</option>
            </select>

            <!-- 市场型资产 -->
            <div v-if="newAsset.asset_style === 'market'" class="market-asset-section">
              <div class="search-input-wrapper">
                <input type="text" v-model="newAsset.symbol" @input="handleSearchInput" placeholder="输入代码/名称自动搜索" autocomplete="off">
                <div v-if="searching" class="loading-spinner"></div>
              </div>

              <ul v-if="searchResults.length > 0" class="search-list">
                <li v-for="r in searchResults" :key="r.symbol" @click="pickSearch(r)">
                  {{ r.symbol }} — {{ r.name }} <span class="muted">({{ r.region || r.currency || r.type }})</span>
                </li>
              </ul>
              <div v-if="searchPerformed && searchResults.length === 0 && newAsset.symbol" class="muted">
                没有找到匹配的结果。
              </div>

              <input type="number" step="any" inputmode="decimal" v-model.number="newAsset.quantity" placeholder="持有份额/股数">
            </div>

            <!-- 固定期限/固收 -->
            <div v-if="newAsset.asset_style === 'fixed'">
              <div class="row">
                <input type="number" step="0.0001" inputmode="decimal" v-model.number="newAsset.rate" placeholder="年化收益率，例如 0.03">
                <select v-model="newAsset.compounding">
                  <option value="annual">年复利</option>
                  <option value="quarterly">季复利</option>
                  <option value="monthly">月复利</option>
                  <option value="simple">单利</option>
                  <option value="continuous">连续复利</option>
                </select>
              </div>
              <div class="row">
                <input type="date" v-model="newAsset.start_date" placeholder="起始日">
                <input type="date" v-model="newAsset.end_date" placeholder="到期日(可选)">
              </div>
              <div class="row">
                <input type="number" step="0.01" inputmode="decimal" v-model.number="newAsset.contribution" placeholder="定投/定存每期金额(可选)">
                <select v-model="newAsset.contribution_freq">
                  <option value="monthly">按月</option>
                  <option value="quarterly">按季</option>
                  <option value="annual">按年</option>
                </select>
              </div>
              <p class="muted">本金请通过“买入”交易录入；现值将按收益率与复利频率自动滚动。</p>
            </div>

            <button type="submit">添加资产</button>
          </form>
        </div>

        <!-- 资产分布图表 -->
        <div class="chart-container">
          <h2>
            资产分布 (按{{ chartMode === 'cost' ? '成本' : '现值' }}查看)
            <button @click="toggleChartMode" class="toggle-btn">切换</button>
          </h2>
          <v-chart class="chart" :option="chartOption" autoresize />
        </div>

        <!-- 历史总资产趋势图（快照） -->
        <div class="chart-container">
          <h2>
            资产趋势（总价值）
            <span>
              <button class="toggle-btn" @click="addSnapshot">记录快照</button>
              <button class="toggle-btn" @click="fetchSnapshots">刷新</button>
            </span>
          </h2>
          <v-chart class="chart" :option="trendOption" autoresize />
        </div>

        <!-- 资产预测走势图（基于模拟的分位数） -->
        <div v-if="simTable.length" class="chart-container">
          <h2>
            资产预测（P50与P5-P95区间）
            <button class="toggle-btn" @click="runSimulate">重新模拟</button>
          </h2>
          <v-chart class="chart" :option="forecastOption" autoresize />
        </div>

        <!-- 模拟结果（分位表） -->
        <div v-if="simTable.length" class="form-container">
          <h2>组合模拟结果（分位数表）</h2>
          <table class="sim-table">
            <thead>
              <tr><th>年份</th><th>P5</th><th>P50</th><th>P95</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in simTable" :key="row.year">
                <td>{{ row.year }}</td>
                <td>¥ {{ row.p5.toFixed(2) }}</td>
                <td>¥ {{ row.p50.toFixed(2) }}</td>
                <td>¥ {{ row.p95.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="column">
        <!-- 资产列表 -->
        <div class="asset-list-container">
          <h2>我的资产 ({{ assets.length }} 项)</h2>
          <ul>
            <li v-for="asset in assets" :key="asset.id" @click="selectAsset(asset)" :class="{ selected: selectedAsset && selectedAsset.id === asset.id }">
              <div class="asset-info">
                <span>{{ asset.name }}</span>
                <span class="asset-type">
                  {{ asset.type }}
                  <template v-if="asset.asset_style === 'market' && asset.symbol"> · {{ asset.symbol }}</template>
                  <template v-if="asset.asset_style === 'fixed'"> · 固收</template>
                </span>
                <span class="profit" :class="asset.profit >= 0 ? 'buy' : 'sell'">收益: ¥ {{ (asset.profit || 0).toFixed(2) }} ({{ (asset.profit_rate || 0).toFixed(2) }}%)</span>
              </div>
              <div class="asset-value">
                <span>现值: ¥ {{ (asset.current_value || 0).toFixed(2) }}</span>
                <button v-if="asset.asset_style==='market' && asset.symbol" @click.stop="refreshQuote(asset)" class="toggle-btn">刷新价格</button>
                <button @click.stop="deleteAsset(asset.id)" class="delete-btn">×</button>
              </div>
            </li>
          </ul>
        </div>

        <!-- 操作面板 -->
        <div v-if="selectedAsset" class="transaction-container">
          <h2>{{ selectedAsset.name }} - 操作面板</h2>
          <form @submit.prevent="updateValue" class="value-form">
            <input v-model.number="tempCurrentValue" type="number" step="0.01" inputmode="decimal" placeholder="输入当前总价值">
            <button type="submit">更新价值</button>
          </form>
          <hr>
          <form @submit.prevent="addTransaction" class="transaction-form">
            <select v-model="newTransaction.type" required>
              <option>买入</option>
              <option>卖出</option>
            </select>
            <input v-model.number="newTransaction.amount" type="number" step="0.01" inputmode="decimal" placeholder="金额" required>
            <button type="submit">添加交易</button>
          </form>
          <ul>
            <li v-for="tx in selectedAsset.transactions" :key="tx.id">
              <span>{{ tx.date }} - {{ tx.type }}</span>
              <span :class="tx.type === '买入' ? 'buy' : 'sell'">¥ {{ tx.amount.toFixed(2) }}</span>
            </li>
          </ul>
        </div>
        <div v-else class="placeholder"><p>请从右侧选择一个资产以进行操作。</p></div>
      </div>
    </section>

    <!-- 收支预算（重构布局） -->
    <section v-if="currentPage==='budget'" class="page budget-page">
      <!-- 顶部工具条（吸顶） -->
      <div class="toolbar sticker">
        <div class="left">
          <label class="muted">月份</label>
          <input type="month" v-model="month" @change="fetchBudget">
          <button class="btn" @click="autofillMonth">一键填充默认</button>
          <button class="btn ghost" @click="fetchBudget">刷新</button>
        </div>
        <div class="right">
          <div class="pill good">收入 ¥ {{ incomeThisMonth.toFixed(2) }}</div>
          <div class="pill bad">支出 ¥ {{ expenseThisMonth.toFixed(2) }}</div>
          <div class="pill" :class="netThisMonth>=0 ? 'good' : 'bad'">结余 ¥ {{ netThisMonth.toFixed(2) }}</div>
        </div>
      </div>

      <div class="budget-grid">
        <!-- 左：快速记一笔 + 固定规则 -->
        <div class="leftcol">
          <div class="card">
            <h3>快速记一笔</h3>
            <form class="row vgap" @submit.prevent="addBudgetEntry">
              <input type="date" v-model="newEntry.date" required>
              <div class="row hgap">
                <select v-model="newEntry.type" style="width:110px;">
                  <option>支出</option>
                  <option>收入</option>
                </select>
                <input type="text" v-model="newEntry.category" placeholder="类别 如：餐饮/工资" required>
              </div>
              <input type="number" step="0.01" inputmode="decimal" v-model.number="newEntry.amount" placeholder="金额" required>
              <input type="text" v-model="newEntry.note" placeholder="备注（可选）">
              <div class="row hgap wrap">
                <div class="chip" v-for="c in hotCategories" :key="c" @click="newEntry.category=c">{{ c }}</div>
              </div>
              <button class="primary" type="submit">添加</button>
            </form>
          </div>

          <div class="card">
            <h3>固定规则（自动默认）</h3>
            <div class="muted" style="margin:-6px 0 8px;">工资、房租、养老金等，支持起止月份与年增长率</div>
            <form class="row vgap" @submit.prevent="addRule">
              <div class="row hgap">
                <select v-model="newRule.type" style="width:110px;">
                  <option>支出</option>
                  <option>收入</option>
                </select>
                <input type="text" v-model="newRule.category" placeholder="类别 如：房租/工资" required>
              </div>
              <div class="row hgap">
                <input type="number" step="0.01" inputmode="decimal" v-model.number="newRule.amount" placeholder="每月金额" required>
                <input type="number" step="0.0001" inputmode="decimal" v-model.number="newRule.growth_rate" placeholder="年增长率(可选) 如0.03">
              </div>
              <div class="row hgap">
                <input type="month" v-model="newRule.start_month" required>
                <input type="month" v-model="newRule.end_month" placeholder="截止(可选)">
              </div>
              <button type="submit">添加规则</button>
            </form>

            <table class="mini-table">
              <thead>
                <tr><th>类型</th><th>类别</th><th style="text-align:right;">金额</th><th>起始</th><th>截止</th><th>增率</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="r in budgetRules" :key="r.id">
                  <td>{{ r.type }}</td>
                  <td>{{ r.category }}</td>
                  <td style="text-align:right;">¥ {{ Number(r.amount).toFixed(2) }}</td>
                  <td>{{ r.start_month }}</td>
                  <td>{{ r.end_month || '-' }}</td>
                  <td>{{ r.growth_rate ? (Number(r.growth_rate)*100).toFixed(1)+'%' : '-' }}</td>
                  <td><button class="icon danger" @click="deleteRule(r.id)">删除</button></td>
                </tr>
                <tr v-if="!budgetRules.length"><td colspan="7" class="muted" style="text-align:center;">暂无规则</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 右：当月明细表 + 过滤和排序 -->
        <div class="rightcol">
          <div class="card">
            <div class="table-toolbar">
              <div class="row hgap wrap">
                <select v-model="filter.type" style="width:120px;">
                  <option value="全部">全部类型</option>
                  <option value="收入">仅收入</option>
                  <option value="支出">仅支出</option>
                </select>
                <select v-model="filter.category" style="width:160px;">
                  <option value="全部">全部类别</option>
                  <option v-for="c in allCategories" :key="c" :value="c">{{ c }}</option>
                </select>
                <input type="search" v-model="filter.q" placeholder="搜索备注/类别..." style="flex:1;min-width:160px;">
                <button class="btn ghost" @click="resetFilters">清空筛选</button>
              </div>
            </div>

            <table class="data-table">
              <thead>
                <tr>
                  <th @click="sortBy('date')">日期 <span class="sort" :class="sortIcon('date')"></span></th>
                  <th @click="sortBy('type')">类型 <span class="sort" :class="sortIcon('type')"></span></th>
                  <th @click="sortBy('category')">类别 <span class="sort" :class="sortIcon('category')"></span></th>
                  <th style="text-align:right;" @click="sortBy('amount')">金额 <span class="sort" :class="sortIcon('amount')"></span></th>
                  <th>备注</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in sortedFilteredEntries" :key="r.id">
                  <td style="white-space:nowrap;">{{ r.date }}</td>
                  <td>{{ r.type }}</td>
                  <td>{{ r.category }}</td>
                  <td style="text-align:right;">¥ {{ Number(r.amount).toFixed(2) }}</td>
                  <td>{{ r.note }}</td>
                  <td><button class="icon danger" @click="deleteBudgetEntry(r.id)">删除</button></td>
                </tr>
                <tr v-if="!sortedFilteredEntries.length"><td colspan="6" class="muted" style="text-align:center;">当月暂无记录</td></tr>
              </tbody>
              <tfoot>
                <tr>
                  <td colspan="3" style="text-align:right;">合计：</td>
                  <td style="text-align:right; font-weight:600;">¥ {{ totalAmountFiltered.toFixed(2) }}</td>
                  <td colspan="2"></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- 财务规划页面 -->
    <section v-if="currentPage==='planning'" class="page">
      <div class="form-container">
        <h2>财务规划参数</h2>
        <form class="row hgap" @submit.prevent="runPlan">
          <label>规划年限</label>
          <input type="number" min="1" v-model.number="planYears" style="width:100px;">
          <label>组合年化收益</label>
          <input type="number" step="0.0001" v-model.number="planReturn" style="width:120px;" placeholder="如 0.06">
          <button class="primary" type="submit">生成财富曲线</button>
        </form>
        <p class="muted">财富曲线=上一月财富×(1+月化收益)+当月净现金流（来自规则：收入-支出；养老金等作为“收入规则”在未来起始月自动纳入）。</p>
      </div>
      <div class="chart-container">
        <v-chart class="chart" :option="planOption" autoresize />
      </div>
    </section>
  </div>
</template>

<script>
import axios from 'axios';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { PieChart, LineChart } from 'echarts/charts';
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent } from 'echarts/components';
import VChart, { THEME_KEY } from 'vue-echarts';

use([ CanvasRenderer, PieChart, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent ]);
const API_URL = 'http://127.0.0.1:5001/api';

export default {
  name: 'App',
  components: { VChart },
  provide: { [THEME_KEY]: 'light' },
  data(){
    const today = new Date();
    const m = today.toISOString().slice(0,7);
    const d = today.toISOString().slice(0,10);
    return {
      currentPage: 'home',
      // —— 财富增值 ——
      assets: [],
      newAsset: { name: '', type: '', initial_cost: null, asset_style: 'manual', symbol: '', quantity: null, rate: null, compounding: 'annual', start_date: '', end_date: '', contribution: null, contribution_freq: 'monthly' },
      selectedAsset: null,
      newTransaction: { type: '买入', amount: null },
      tempCurrentValue: null,
      chartMode: 'value',
      searching: false,
      searchResults: [],
      simTable: [],
      debounceTimer: null,
      searchPerformed: false,
      snapshots: [],
      // —— 收支预算 ——
      month: m,
      budgetEntries: [],
      budgetRules: [],
      newEntry: { date: d, type: '支出', category: '', amount: null, note: '' },
      newRule: { type: '支出', category: '', amount: null, start_month: m, end_month: '', growth_rate: 0 },
      incomeThisMonth: 0,
      expenseThisMonth: 0,
      filter: { type: '全部', category: '全部', q: '' },
      sort: { key: 'date', dir: 'desc' },
      // —— 财务规划 ——
      planYears: 30,
      planReturn: 0.06,
      planSeries: []
    };
  },
  computed: {
    // —— 财富增值 ——
    totalCurrentValue(){ return this.assets.reduce((s,a)=>s+(a.current_value||0),0); },
    totalProfit(){ return this.assets.reduce((s,a)=>s+(a.profit||0),0); },
    chartOption(){
      const dataKey = this.chartMode === 'cost' ? 'total_cost' : 'current_value';
      const distribution = this.assets.reduce((acc, asset) => {
        const value = asset[dataKey] || 0;
        if (value > 0) {
          const key = (asset.type || '其他') + (asset.asset_style === 'fixed' ? '(固收)' : '');
          acc[key] = (acc[key] || 0) + value;
        }
        return acc;
      }, {});
      const dataForChart = Object.keys(distribution).map(key => ({ name: key, value: distribution[key] }));
      return { tooltip: { trigger: 'item', formatter: '{a} <br/>{b} : ¥ {c} ({d}%)' }, legend: { orient: 'vertical', left: 'left', data: Object.keys(distribution) }, series: [{ name: '资产类型', type: 'pie', radius: '70%', center: ['65%', '50%'], data: dataForChart }] };
    },
    trendOption(){
      const d = (this.snapshots || []).map(s => ({ value: [s.created_at, s.total_value] }));
      const fmt = v => '¥ ' + (Number(v) || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      return { tooltip: { trigger: 'axis', valueFormatter: (val) => fmt(val) }, grid: { left: 48, right: 24, top: 36, bottom: 50 }, xAxis: { type: 'time' }, yAxis: { type: 'value' }, dataZoom: [ { type: 'inside' }, { type: 'slider', height: 18, bottom: 12 } ], series: [ { name: '总资产', type: 'line', showSymbol: false, data: d } ] };
    },
    forecastOption(){
      const cats = this.simTable.map(r => `第${r.year}年`);
      const p5 = this.simTable.map(r => r.p5);
      const p50 = this.simTable.map(r => r.p50);
      const p95 = this.simTable.map(r => r.p95);
      const band = p95.map((v, i) => v - p5[i]);
      const fmt = v => '¥ ' + (Number(v) || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      return { tooltip: { trigger: 'axis', valueFormatter: (val) => fmt(val) }, legend: { data: ['P50', 'P5-P95 区间'] }, grid: { left: 48, right: 24, top: 36, bottom: 50 }, xAxis: { type: 'category', data: cats }, yAxis: { type: 'value' }, series: [ { name: 'P5 基线', type: 'line', data: p5, showSymbol: false, lineStyle: { width: 0 }, stack: 'band', areaStyle: { opacity: 0 } }, { name: 'P5-P95 区间', type: 'line', data: band, showSymbol: false, stack: 'band', areaStyle: { } }, { name: 'P50', type: 'line', data: p50, showSymbol: true } ] };
    },
    // —— 收支预算 ——
    netThisMonth(){ return this.incomeThisMonth - this.expenseThisMonth; },
    allCategories(){
      const set = new Set();
      this.budgetEntries.forEach(r => set.add(r.category));
      this.budgetRules.forEach(r => set.add(r.category));
      return Array.from(set);
    },
    hotCategories(){
      const freq = new Map();
      this.budgetEntries.slice(-30).forEach(r => freq.set(r.category, (freq.get(r.category)||0)+1));
      return Array.from(freq.entries()).sort((a,b)=>b[1]-a[1]).slice(0,10).map(([c])=>c);
    },
    filteredEntries(){
      return this.budgetEntries.filter(r => {
        if(this.filter.type!=='全部' && r.type!==this.filter.type) return false;
        if(this.filter.category!=='全部' && r.category!==this.filter.category) return false;
        if(this.filter.q){
          const q=this.filter.q.trim().toLowerCase();
          const str=(r.category+' '+(r.note||'')).toLowerCase();
          if(!str.includes(q)) return false;
        }
        return true;
      });
    },
    sortedFilteredEntries(){
      const arr=[...this.filteredEntries];
      const k=this.sort.key; const dir=this.sort.dir==='asc'?1:-1;
      arr.sort((a,b)=>{
        let va=a[k], vb=b[k];
        if(k==='date'){ va=new Date(a.date).getTime(); vb=new Date(b.date).getTime(); }
        if(va<vb) return -1*dir; if(va>vb) return 1*dir; return 0;
      });
      return arr;
    },
    totalAmountFiltered(){
      return this.sortedFilteredEntries.reduce((s,r)=>s+Number(r.amount||0),0);
    },
    // —— 财务规划 ——
    planOption(){
      const cats=this.planSeries.map(p=>p.month);
      const wealth=this.planSeries.map(p=>p.wealth);
      const income=this.planSeries.map(p=>p.income);
      const expense=this.planSeries.map(p=>p.expense);
      const fmt=v=>'¥ '+(Number(v)||0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      return { tooltip:{ trigger:'axis', valueFormatter:(val)=>fmt(val) }, legend:{ data:['财富','收入','支出'] }, grid:{ left:48, right:24, top:36, bottom:50 }, xAxis:{ type:'category', data:cats }, yAxis:{ type:'value' }, dataZoom:[{type:'inside'},{type:'slider',height:16,bottom:10}], series:[ {name:'财富', type:'line', data:wealth, showSymbol:false}, {name:'收入', type:'line', data:income, showSymbol:false}, {name:'支出', type:'line', data:expense, showSymbol:false} ] };
    }
  },
  methods: {
    // —— 导航 ——
    go(p){ this.currentPage=p; if(p==='budget'){ this.fetchBudget(); this.fetchRules(); } if(p==='planning'){ this.runPlan(); } },

    // —— 财富增值 ——
    async fetchAssets(){ try{ const {data}=await axios.get(`${API_URL}/assets`); this.assets=data; }catch(e){ console.error('获取资产失败',e);} },
    async addAsset(){
      try{
        const payload={...this.newAsset};
        if(payload.initial_cost!==null && payload.initial_cost<0){ alert('初始成本不能为负数！'); return; }
        if(!payload.symbol) delete payload.symbol;
        if(!payload.quantity && payload.quantity!==0) delete payload.quantity;
        if(payload.asset_style!=='fixed'){ delete payload.rate; delete payload.compounding; delete payload.start_date; delete payload.end_date; delete payload.contribution; delete payload.contribution_freq; }
        const {data:created}=await axios.post(`${API_URL}/assets`,payload);
        let updated=created;
        if(payload.initial_cost && payload.initial_cost>0){ const {data:withTx}=await axios.post(`${API_URL}/assets/${created.id}/transactions`,{type:'买入',amount:payload.initial_cost}); updated=withTx; }
        this.assets.push(updated);
        this.newAsset={ name:'', type:'', initial_cost:null, asset_style:'manual', symbol:'', quantity:null, rate:null, compounding:'annual', start_date:'', end_date:'', contribution:null, contribution_freq:'monthly' };
        this.searchResults=[];
      }catch(e){ console.error('添加资产失败',e); alert('添加资产失败，请检查控制台信息。'); }
    },
    async deleteAsset(id){ if(confirm('确定要删除这个资产及其所有交易记录吗？')){ try{ await axios.delete(`${API_URL}/assets/${id}`); this.assets=this.assets.filter(a=>a.id!==id); if(this.selectedAsset && this.selectedAsset.id===id){ this.selectedAsset=null; } }catch(e){ console.error('删除资产失败',e);} } },
    selectAsset(a){ this.selectedAsset=a; this.tempCurrentValue=a.current_value; },
    async addTransaction(){ try{ const {data}=await axios.post(`${API_URL}/assets/${this.selectedAsset.id}/transactions`,this.newTransaction); this.updateLocalAssetData(data); this.newTransaction.amount=null; }catch(e){ console.error('添加交易失败',e);} },
    async updateValue(){ try{ const {data}=await axios.put(`${API_URL}/assets/${this.selectedAsset.id}/value`,{current_value:this.tempCurrentValue}); this.updateLocalAssetData(data); alert('当前价值已更新！'); }catch(e){ console.error('更新价值失败',e);} },
    toggleChartMode(){ this.chartMode=this.chartMode==='cost'?'value':'cost'; },
    updateLocalAssetData(updated){ if(!updated) return; const norm=v=>(v!=null?String(v):v); const id=norm(updated.id??updated.asset_id); const idx=this.assets.findIndex(a=>norm(a.id)===id); if(idx!==-1) this.assets[idx]={...this.assets[idx],...updated,id:updated.id}; if(this.selectedAsset && norm(this.selectedAsset.id)===id){ this.selectedAsset={...this.selectedAsset,...updated,id:updated.id}; this.tempCurrentValue=this.selectedAsset.current_value; } if(idx===-1 && this.selectedAsset){ const sid=norm(this.selectedAsset.id); const sidx=this.assets.findIndex(a=>norm(a.id)===sid); if(sidx!==-1) this.assets[sidx]={...this.assets[sidx],...updated,id:updated.id??this.assets[sidx].id}; } },
    handleSearchInput(){ clearTimeout(this.debounceTimer); this.searchPerformed=false; if(!(this.newAsset.symbol||'').trim()){ this.searchResults=[]; return; } this.debounceTimer=setTimeout(()=>{ this.doSearch(); },500); },
    async doSearch(){ const q=(this.newAsset.symbol||'').trim(); if(!q) return; this.searching=true; this.searchResults=[]; this.searchPerformed=false; try{ const {data}=await axios.get(`${API_URL}/search`,{params:{q}}); this.searchResults=data||[]; }catch(e){ console.error(e); this.searchResults=[]; }finally{ this.searching=false; this.searchPerformed=true; } },
    pickSearch(r){ this.newAsset.symbol=r.symbol; if(!this.newAsset.name) this.newAsset.name=r.name||r.symbol; this.searchResults=[]; this.searchPerformed=false; },
    async refreshQuote(a){ if(!a.symbol) return; try{ const {data}=await axios.get(`${API_URL}/quote`,{params:{symbol:a.symbol}}); const newCV=(data.price||0)*(a.quantity||0); const {data:updated}=await axios.put(`${API_URL}/assets/${a.id}/value`,{current_value:newCV}); this.updateLocalAssetData(updated); }catch(e){ console.error(e);} },
    async fetchSnapshots(){ try{ const {data}=await axios.get(`${API_URL}/snapshots`,{params:{limit:500}}); this.snapshots=data||[]; }catch(e){ console.error('获取快照失败',e);} },
    async addSnapshot(){ try{ const {data}=await axios.post(`${API_URL}/snapshots`); this.snapshots=[...this.snapshots,data].sort((a,b)=>new Date(a.created_at)-new Date(b.created_at)); }catch(e){ console.error('记录快照失败',e); alert('记录失败，请查看控制台。'); } },
    async runSimulate(){ try{ const total=this.totalCurrentValue||1; const assets=this.assets.map(a=>{ const w=Math.max(0,(a.current_value||0))/total; let mu=0.03, sigma=0.05; if(a.type==='股票'){ mu=0.08; sigma=0.2;} if(a.type==='基金'){ mu=0.06; sigma=0.15;} if(a.asset_style==='fixed'){ mu=a.rate||0.03; sigma=0.01;} return {id:a.id, weight:w, mu, sigma}; }); const body={ years:5, steps_per_year:12, n_paths:2000, assets, start_value:this.totalCurrentValue }; const {data}=await axios.post(`${API_URL}/simulate`,body); this.simTable=data.table||[]; if(!this.simTable.length) alert('模拟结果为空，请检查参数。'); }catch(e){ console.error(e); alert('模拟失败，请检查控制台错误信息。'); } },

    // —— 收支预算 ——
    monthBounds(){ const [y,m]=this.month.split('-').map(x=>parseInt(x,10)); const start=`${y}-${String(m).padStart(2,'0')}-01`; const end=new Date(y,m,0).toISOString().slice(0,10); return {start,end}; },
    async fetchBudget(){ try{ const {start,end}=this.monthBounds(); const {data}=await axios.get(`${API_URL}/budget/entries`,{params:{start,end}}); this.budgetEntries=data||[]; await this.fetchBudgetSummary(); }catch(e){ console.error('获取预算失败',e);} },
    async fetchBudgetSummary(){ try{ const {start,end}=this.monthBounds(); const {data}=await axios.get(`${API_URL}/budget/summary`,{params:{start,end}}); this.incomeThisMonth=data.income||0; this.expenseThisMonth=data.expense||0; }catch(e){ console.error('获取预算汇总失败',e);} },
    async addBudgetEntry(){ try{ const payload={...this.newEntry}; if(!payload.category || !payload.amount || !payload.date){ alert('请完整填写日期/类型/类别/金额'); return; } const {data}=await axios.post(`${API_URL}/budget/entries`,payload); this.budgetEntries=[...this.budgetEntries,data]; this.newEntry={ ...this.newEntry, category:'', amount:null, note:'' }; await this.fetchBudgetSummary(); }catch(e){ console.error('新增收支失败',e);} },
    async deleteBudgetEntry(id){ if(confirm('删除该记录？')){ try{ await axios.delete(`${API_URL}/budget/entries/${id}`); this.budgetEntries=this.budgetEntries.filter(r=>r.id!==id); await this.fetchBudgetSummary(); }catch(e){ console.error('删除失败',e);} } },
    async fetchRules(){ try{ const {data}=await axios.get(`${API_URL}/budget/rules`); this.budgetRules=(data||[]); }catch(e){ console.error('获取规则失败',e);} },
    async addRule(){ try{ const p={...this.newRule}; if(!p.category||!p.amount||!p.start_month){ alert('请填写类型/类别/金额/起始月份'); return; } const {data}=await axios.post(`${API_URL}/budget/rules`,p); this.budgetRules=[...this.budgetRules,data]; this.newRule={ type:'支出', category:'', amount:null, start_month:this.month, end_month:'', growth_rate:0 }; }catch(e){ console.error('新增规则失败',e);} },
    async deleteRule(id){ if(confirm('删除该规则？')){ try{ await axios.delete(`${API_URL}/budget/rules/${id}`); this.budgetRules=this.budgetRules.filter(r=>r.id!==id); }catch(e){ console.error('删除规则失败',e);} } },
    async autofillMonth(){ try{ const {start}=this.monthBounds(); const month=start.slice(0,7); const {data}=await axios.post(`${API_URL}/budget/autofill`,{ month }); if(Array.isArray(data)){ await this.fetchBudget(); alert(`已填充 ${data.length} 条默认项目`); } }catch(e){ console.error('一键填充失败',e); alert('填充失败，请查看控制台。'); } },
    sortBy(k){ if(this.sort.key===k){ this.sort.dir=this.sort.dir==='asc'?'desc':'asc'; } else { this.sort.key=k; this.sort.dir='asc'; } },
    sortIcon(k){ if(this.sort.key!==k) return ''; return this.sort.dir==='asc'?'asc':'desc'; },
    resetFilters(){ this.filter={ type:'全部', category:'全部', q:'' }; },

    // —— 财务规划 ——
    async runPlan(){ try{ const body={ years:this.planYears, annual_return:this.planReturn }; const {data}=await axios.post(`${API_URL}/plan/curve`,body); this.planSeries=data.points||[]; }catch(e){ console.error('生成规划失败',e);} }
  },
  created(){ this.fetchAssets(); this.fetchSnapshots(); this.fetchBudget(); this.fetchRules(); }
};
</script>

<style>
#app { font-family: Avenir, Helvetica, Arial, sans-serif; max-width: 1400px; margin: 32px auto; color: #2c3e50; }
header { text-align: center; margin-bottom: 16px; }
.nav { display: inline-flex; gap: 8px; }
.nav button { padding: 6px 12px; border: 1px solid #ddd; background: #fff; border-radius: 8px; cursor: pointer; }
.nav button.active { background: #42b983; color: #fff; border-color: #42b983; }

.page { display: flex; gap: 40px; }
.column { flex: 1; display: flex; flex-direction: column; gap: 20px; }
.form-container, .asset-list-container, .transaction-container, .placeholder, .chart-container { border: 1px solid #eaeaea; border-radius: 8px; padding: 20px; background:#fff; }
h2 { margin-top: 0; display: flex; justify-content: space-between; align-items: center; }
.toggle-btn { padding: 4px 8px; font-size: 12px; background-color: #eee; color: #333; border: 1px solid #ddd; border-radius: 6px; }
.chart-container { height: 360px; }
.chart { height: 100%; }
.profit { font-size: 12px; }
.buy { color: green; }
.sell { color: red; }
.value-form { display: flex; gap: 10px; margin-bottom: 20px; padding-bottom:20px; border-bottom: 1px solid #eee; }
.value-form input { flex: 1; }
ul { list-style: none; padding: 0; margin: 0; }
li { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }
li:hover { background-color: #f9f9f9; }
li.selected { background-color: #e8f5e9; }
.asset-info { display: flex; flex-direction: column; }
.asset-type { font-size: 12px; color: #777; }
.asset-value { display: flex; align-items: center; gap: 10px; }
.delete-btn { background-color: #e57373; color: white; border-radius: 50%; width: 24px; height: 24px; padding: 0; line-height: 24px; text-align: center; font-size: 14px; border: none; cursor: pointer; }
input, select, button { padding: 10px; font-size: 16px; border-radius: 8px; border: 1px solid #ddd; margin-top: 8px; }
button { background-color: #42b983; color: white; border: none; cursor: pointer; }
button:hover { background-color: #36a476; }
.transaction-form { display: flex; gap: 10px; margin-bottom: 20px; }
.transaction-form input { flex: 1; }
.placeholder { text-align: center; padding: 100px 20px; color: #999; }
.row { display: flex; gap: 8px; }
.search-list { max-height: 180px; overflow: auto; border: 1px solid #eee; border-radius: 6px; padding: 6px; margin: 0; background:#fff; }
.search-list li { padding: 6px 8px; border-bottom: 1px solid #f1f1f1; }
.search-list li:last-child { border-bottom: 0; }
.muted { font-size: 12px; color: #777; margin-top: 6px; }
.sim-table { width: 100%; border-collapse: collapse; }
.sim-table th, .sim-table td { border: 1px solid #eee; padding: 8px; text-align: left; }
.sim-table td:nth-child(4), .sim-table th:nth-child(4) { text-align: right; }
.sim-table th:first-child, .sim-table td:first-child { white-space: nowrap; }
.market-asset-section { display: flex; flex-direction: column; gap: 8px; }
.search-input-wrapper { position: relative; width: 100%; }
.search-input-wrapper input { width: 100%; box-sizing: border-box; }
.loading-spinner { border: 3px solid rgba(0, 0, 0, 0.1); width: 18px; height: 18px; border-radius: 50%; border-left-color: #42b983; animation: spin 1s ease infinite; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); }
@keyframes spin { 0% { transform: translateY(-50%) rotate(0deg); } 100% { transform: translateY(-50%) rotate(360deg); }
}

/* 主页样式 */
.home .hero { border: 1px solid #eaeaea; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 20px; background:#fff; }
.home .cta { display: flex; justify-content: center; gap: 12px; margin-top: 12px; }
.home .primary { background: #42b983; color:#fff; border:none; padding:10px 16px; border-radius:8px; }
.home .secondary { background: #fff; color:#42b983; border:1px solid #42b983; padding:10px 16px; border-radius:8px; }
.quick-cards { display: grid; grid-template-columns: repeat(2,1fr); gap: 16px; }
.card { border:1px solid #eaeaea; border-radius:12px; padding:16px; background:#fff; }
.card .big { font-size: 20px; font-weight: bold; }

/* 预算页布局 */
.toolbar { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:12px 16px; border:1px solid #eaeaea; border-radius:12px; background:#fff; margin-bottom:16px; }
.sticker { position: sticky; top: 8px; z-index: 2; }
.toolbar .left { display:flex; align-items:center; gap:8px; }
.toolbar .right { display:flex; align-items:center; gap:8px; }
.pill { padding:6px 10px; border-radius:999px; background:#f6f6f6; font-weight:600; }
.pill.good { background:#e9f7ef; color:#1e7e34; }
.pill.bad { background:#fdecea; color:#b02a37; }

.budget-grid { display:grid; grid-template-columns: 1fr 2fr; gap:16px; align-items:start; }
.leftcol .card, .rightcol .card { border:1px solid #eaeaea; border-radius:12px; padding:16px; background:#fff; }

.row { display:flex; }
.wrap { flex-wrap: wrap; }
.hgap { gap:8px; }
.vgap { flex-direction: column; gap:8px; }
.btn { padding:6px 10px; border:1px solid #ddd; background:#fff; border-radius:8px; cursor:pointer; }
.btn.ghost { background:#fafafa; }
.primary { background:#42b983; color:#fff; border:none; padding:10px 14px; border-radius:10px; cursor:pointer; }
.icon { padding:4px 8px; border:1px solid #eee; border-radius:6px; background:#fff; cursor:pointer; }
.icon.danger { color:#b02a37; border-color:#f3c2c2; }

input, select { padding:10px; border:1px solid #ddd; border-radius:8px; }
.linkish { background:none; border:none; color:#42b983; cursor:pointer; text-decoration:underline; }

.mini-table, .data-table { width:100%; border-collapse: collapse; margin-top:10px; }
.mini-table th, .mini-table td, .data-table th, .data-table td { border-bottom:1px solid #f0f0f0; padding:8px; text-align:left; }
.data-table tfoot td { border-top:2px solid #f0f0f0; }
.table-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.sort { display:inline-block; width:0; height:0; border-left:4px solid transparent; border-right:4px solid transparent; margin-left:4px; }
.sort.asc { border-bottom:6px solid #999; }
.sort.desc { border-top:6px solid #999; }

/* Chips */
.chip { padding:4px 8px; border-radius:999px; background:#f3f3f3; cursor:pointer; border:1px solid #e8e8e8; }
.chip:hover { background:#ececec; }
</style>


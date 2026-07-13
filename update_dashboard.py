# -*- coding: utf-8 -*-
"""
黄金海龟交易策略 - 每日数据更新脚本
用于 GitHub Actions 自动更新
"""
import tushare as ts
import pandas as pd
import numpy as np
import json
import os
import base64

# ============================================================
# 配置参数
# ============================================================
# Tushare token: 优先从环境变量读取，否则使用默认值
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', 'f17f27bdd055aca576e857d5d8a739581426a9482ddc991b014fa560')
INITIAL_CAPITAL = 100000.0
CHANNEL_PERIOD = 20
ATR_PERIOD = 14
ATR_MULTIPLIER = 2
RISK_PER_TRADE = 0.02
COMMISSION_RATE = 0.0003
SLIPPAGE = 0.001

OUTPUT_FILE = 'gold_turtle_dashboard.html'

print("=" * 60)
print("黄金海龟交易策略 - 每日更新")
print("=" * 60)

# ============================================================
# 1. 获取数据
# ============================================================
print("\n[1/6] 获取黄金价格数据...")
ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

df = pro.daily(ts_code='600547.SH', start_date='20160713', end_date='20260713')
if df is None or len(df) == 0:
    print("错误: 未获取到数据!")
    exit(1)

df = df.sort_values('trade_date').reset_index(drop=True)
df['trade_date'] = pd.to_datetime(df['trade_date'])
df.rename(columns={
    'open': 'Open', 'high': 'High', 'low': 'Low',
    'close': 'Close', 'vol': 'Volume', 'amount': 'Amount'
}, inplace=True)

print(f"  记录数: {len(df)}, 时间: {df['trade_date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['trade_date'].iloc[-1].strftime('%Y-%m-%d')}")

# ============================================================
# 2. 计算指标
# ============================================================
print("[2/6] 计算 Donchian 通道 & ATR...")

# Donchian 通道
df['Upper_Channel'] = df['High'].rolling(window=CHANNEL_PERIOD).max().shift(1)
df['Lower_Channel'] = df['Low'].rolling(window=CHANNEL_PERIOD).min().shift(1)
df['Middle_Channel'] = (df['Upper_Channel'] + df['Lower_Channel']) / 2

# ATR
df['TR'] = np.maximum(
    df['High'] - df['Low'],
    np.maximum(
        abs(df['High'] - df['Close'].shift(1)),
        abs(df['Low'] - df['Close'].shift(1))
    )
)
df['ATR'] = df['TR'].rolling(window=ATR_PERIOD).mean()
df['ATR_Pct'] = df['ATR'] / df['Close'] * 100

# 交易信号
df['Buy_Signal'] = (df['Close'] > df['Upper_Channel']) & (df['Close'].shift(1) <= df['Upper_Channel'].shift(1))
df['Sell_Signal'] = (df['Close'] < df['Lower_Channel']) & (df['Close'].shift(1) >= df['Lower_Channel'].shift(1))

print(f"  上轨最新: {df['Upper_Channel'].iloc[-1]:.2f}, 下轨最新: {df['Lower_Channel'].iloc[-1]:.2f}")
print(f"  ATR最新: {df['ATR'].iloc[-1]:.4f}")
print(f"  买入信号: {df['Buy_Signal'].sum()}, 卖出信号: {df['Sell_Signal'].sum()}")

# ============================================================
# 3. 回测
# ============================================================
print("[3/6] 策略回测...")

position = 0
entry_price = 0
stop_loss_price = 0
capital = INITIAL_CAPITAL
peak_capital = INITIAL_CAPITAL
entry_commission = 0
entry_date = None
trades = []
equity_curve = []

for i in range(len(df)):
    row = df.iloc[i]
    date = row['trade_date']
    close = row['Close']
    high = row['High']
    low = row['Low']
    atr = row['ATR']
    upper = row['Upper_Channel']
    lower = row['Lower_Channel']

    # 止损检查
    if position > 0 and stop_loss_price > 0:
        if low <= stop_loss_price:
            sell_price = stop_loss_price * (1 - SLIPPAGE)
            trade_value = position * sell_price
            commission = trade_value * COMMISSION_RATE
            capital += trade_value - commission
            pnl = (sell_price - entry_price) * position - commission - entry_commission
            trades.append({
                'entry_date': entry_date,
                'exit_date': date,
                'entry_price': entry_price,
                'exit_price': sell_price,
                'position': position,
                'pnl': round(pnl, 2),
                'return_pct': round(pnl / (entry_price * position) * 100, 2),
                'exit_type': '止损',
                'hold_days': (date - entry_date).days
            })
            position = 0
            entry_price = 0
            stop_loss_price = 0

    # 买入信号
    if row['Buy_Signal'] and position == 0 and not pd.isna(atr) and atr > 0:
        risk_amount = capital * RISK_PER_TRADE
        shares = int(risk_amount / (ATR_MULTIPLIER * atr) / 100) * 100
        if shares > 0:
            entry_price = close * (1 + SLIPPAGE)
            position = shares
            stop_loss_price = entry_price - ATR_MULTIPLIER * atr
            trade_cost = position * entry_price
            entry_commission = trade_cost * COMMISSION_RATE
            capital -= trade_cost + entry_commission
            entry_date = date

    # 卖出信号
    elif row['Sell_Signal'] and position > 0:
        sell_price = close * (1 - SLIPPAGE)
        trade_value = position * sell_price
        commission = trade_value * COMMISSION_RATE
        capital += trade_value - commission
        pnl = (sell_price - entry_price) * position - commission - entry_commission
        trades.append({
            'entry_date': entry_date,
            'exit_date': date,
            'entry_price': entry_price,
            'exit_price': sell_price,
            'position': position,
            'pnl': round(pnl, 2),
            'return_pct': round(pnl / (entry_price * position) * 100, 2),
            'exit_type': '信号卖出',
            'hold_days': (date - entry_date).days
        })
        position = 0
        entry_price = 0
        stop_loss_price = 0

    # 移动止损
    if position > 0 and not pd.isna(atr) and atr > 0:
        new_stop = close - ATR_MULTIPLIER * atr
        if new_stop > stop_loss_price:
            stop_loss_price = new_stop

    total_equity = capital + position * close
    equity_curve.append({
        'date': date,
        'equity': round(total_equity, 2),
        'close': close,
        'position': position,
        'stop_loss': round(stop_loss_price, 2) if position > 0 else None
    })
    if total_equity > peak_capital:
        peak_capital = total_equity

# 期末平仓
if position > 0:
    close_price = df.iloc[-1]['Close'] * (1 - SLIPPAGE)
    trade_value = position * close_price
    commission = trade_value * COMMISSION_RATE
    capital += trade_value - commission
    pnl = (close_price - entry_price) * position - commission - entry_commission
    trades.append({
        'entry_date': entry_date,
        'exit_date': df.iloc[-1]['trade_date'],
        'entry_price': entry_price,
        'exit_price': close_price,
        'position': position,
        'pnl': round(pnl, 2),
        'return_pct': round(pnl / (entry_price * position) * 100, 2),
        'exit_type': '期末平仓',
        'hold_days': (df.iloc[-1]['trade_date'] - entry_date).days
    })

equity_df = pd.DataFrame(equity_curve)
trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()

print(f"  交易次数: {len(trades)}")
print(f"  最终资产: ¥{equity_df['equity'].iloc[-1]:,.2f}")

# ============================================================
# 4. 计算指标
# ============================================================
print("[4/6] 计算量化指标...")

total_return = (equity_df['equity'].iloc[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
years = (df['trade_date'].iloc[-1] - df['trade_date'].iloc[0]).days / 365.25
annual_return = ((equity_df['equity'].iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100

equity_df['peak'] = equity_df['equity'].cummax()
equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
max_drawdown = equity_df['drawdown'].min()

equity_df['daily_return'] = equity_df['equity'].pct_change()
rf = 0.025
sharpe = (equity_df['daily_return'].mean() * 252 - rf) / (equity_df['daily_return'].std() * np.sqrt(252)) if equity_df['daily_return'].std() > 0 else 0
annual_volatility = equity_df['daily_return'].std() * np.sqrt(252) * 100

sortino = 0
downside = equity_df['daily_return'][equity_df['daily_return'] < 0]
if len(downside) > 0 and downside.std() > 0:
    sortino = (equity_df['daily_return'].mean() * 252 - rf) / (downside.std() * np.sqrt(252))

total_trades = len(trades_df)
win_trades = len(trades_df[trades_df['pnl'] > 0]) if total_trades > 0 else 0
loss_trades = len(trades_df[trades_df['pnl'] <= 0]) if total_trades > 0 else 0
win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0

avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if win_trades > 0 else 0
avg_loss = trades_df[trades_df['pnl'] <= 0]['pnl'].mean() if loss_trades > 0 else 0
profit_factor = abs(trades_df[trades_df['pnl'] > 0]['pnl'].sum() / trades_df[trades_df['pnl'] <= 0]['pnl'].sum()) if loss_trades > 0 and trades_df[trades_df['pnl'] <= 0]['pnl'].sum() != 0 else float('inf')
avg_hold_days = trades_df['hold_days'].mean() if total_trades > 0 else 0

buy_hold_return = (df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0] * 100
buy_hold_annual = ((df['Close'].iloc[-1] / df['Close'].iloc[0]) ** (1 / years) - 1) * 100

calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else float('inf')

metrics = {
    'initial_capital': INITIAL_CAPITAL,
    'final_equity': round(equity_df['equity'].iloc[-1], 2),
    'total_return': round(total_return, 2),
    'annual_return': round(annual_return, 2),
    'max_drawdown': round(max_drawdown, 2),
    'sharpe': round(sharpe, 3),
    'sortino': round(sortino, 3),
    'calmar': round(calmar, 2) if calmar != float('inf') else None,
    'win_rate': round(win_rate, 1),
    'total_trades': total_trades,
    'win_trades': win_trades,
    'loss_trades': loss_trades,
    'avg_win': round(avg_win, 2),
    'avg_loss': round(abs(avg_loss), 2),
    'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else None,
    'avg_hold_days': round(avg_hold_days, 0),
    'annual_volatility': round(annual_volatility, 2),
    'buy_hold_return': round(buy_hold_return, 2),
    'buy_hold_annual': round(buy_hold_annual, 2),
    'years': round(years, 1),
    'last_update': df['trade_date'].iloc[-1].strftime('%Y-%m-%d'),
    'data_range': f"{df['trade_date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['trade_date'].iloc[-1].strftime('%Y-%m-%d')}",
    'stock_code': '600547.SH',
    'stock_name': '山东黄金'
}

print(f"  总收益率: {total_return:.2f}%, 夏普: {sharpe:.3f}")

# ============================================================
# 5. 准备图表数据
# ============================================================
print("[5/6] 准备图表数据...")

df['date_str'] = df['trade_date'].dt.strftime('%Y-%m-%d')
equity_df['date_str'] = equity_df['date'].dt.strftime('%Y-%m-%d')

def clean_val(v):
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return None
    if isinstance(v, (np.floating, float)):
        return round(float(v), 4)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime('%Y-%m-%d')
    return v

chart_data = {
    'dates': [clean_val(d) for d in df['date_str'].tolist()],
    'close': [clean_val(c) for c in df['Close'].tolist()],
    'high': [clean_val(h) for h in df['High'].tolist()],
    'low': [clean_val(l) for l in df['Low'].tolist()],
    'open': [clean_val(o) for o in df['Open'].tolist()],
    'volume': [clean_val(v) for v in df['Volume'].tolist()],
    'upper_channel': [clean_val(u) for u in df['Upper_Channel'].tolist()],
    'lower_channel': [clean_val(l) for l in df['Lower_Channel'].tolist()],
    'middle_channel': [clean_val(m) for m in df['Middle_Channel'].tolist()],
    'atr': [clean_val(a) for a in df['ATR'].tolist()],
    'atr_pct': [clean_val(a) for a in df['ATR_Pct'].tolist()],
    'buy_signals': [clean_val(d) for d in df[df['Buy_Signal']]['date_str'].tolist()],
    'buy_prices': [clean_val(c) for c in df[df['Buy_Signal']]['Close'].tolist()],
    'sell_signals': [clean_val(d) for d in df[df['Sell_Signal']]['date_str'].tolist()],
    'sell_prices': [clean_val(c) for c in df[df['Sell_Signal']]['Close'].tolist()],
    'equity_dates': [clean_val(d) for d in equity_df['date_str'].tolist()],
    'equity': [clean_val(e) for e in equity_df['equity'].tolist()],
    'drawdown': [clean_val(d) for d in equity_df['drawdown'].tolist()],
    'daily_returns': [clean_val(r) if pd.notna(r) else 0 for r in equity_df['daily_return'].tolist()],
    'trades': [],
    'metrics': metrics
}

for _, t in trades_df.iterrows():
    trade = {}
    for col in trades_df.columns:
        trade[col] = clean_val(t[col])
    if 'entry_date' in trade and isinstance(trade['entry_date'], str):
        pass  # already a string
    if 'exit_date' in trade and isinstance(trade['exit_date'], str):
        pass
    chart_data['trades'].append(trade)

print(f"  交易日: {len(chart_data['dates'])}, 交易记录: {len(chart_data['trades'])}")

# ============================================================
# 6. 生成 HTML
# ============================================================
print("[6/6] 生成 HTML 看板...")

data_json = json.dumps(chart_data, ensure_ascii=False)

html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>黄金海龟交易策略看板</title>
<script src="https://cdn.plot.ly/plotly-2.27.1.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }
.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: white; padding: 28px 40px; }
.header h1 { font-size: 28px; margin-bottom: 8px; }
.header .subtitle { font-size: 14px; color: #a0aec0; }
.header .update-info { font-size: 12px; color: #718096; margin-top: 6px; }
.metrics-row { display: flex; flex-wrap: wrap; gap: 16px; padding: 24px 40px; }
.metric-card { background: white; border-radius: 12px; padding: 18px 22px; min-width: 160px; flex: 1; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.metric-card .label { font-size: 12px; color: #718096; margin-bottom: 4px; }
.metric-card .value { font-size: 22px; font-weight: 700; }
.metric-card .change { font-size: 12px; margin-top: 2px; }
.positive { color: #e74c3c; }
.negative { color: #27ae60; }
.chart-container { padding: 0 40px 20px; }
.chart-box { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }
.chart-box .chart-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; color: #2d3748; }
.chart-box .chart-wrap { width: 100%; }
.trades-table { padding: 0 40px 40px; }
.trades-table table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.trades-table th { background: #f7fafc; padding: 12px 16px; font-size: 12px; color: #4a5568; text-align: left; font-weight: 600; }
.trades-table td { padding: 10px 16px; font-size: 13px; border-top: 1px solid #e2e8f0; }
.trade-win { color: #e74c3c; }
.trade-loss { color: #27ae60; }
</style>
</head>
<body>

<div class="header">
<h1>🏦 黄金海龟交易策略看板</h1>
<div class="subtitle">标的海龟交易法则 · Donchian 通道突破 + ATR 动态止损</div>
<div class="update-info">
<span>标的: {stock_code} {stock_name}</span> · 
<span>数据范围: {data_range}</span> · 
<span>最后更新: {last_update}</span> · 
<span>自动更新: 每日收盘后</span>
</div>
</div>

<div class="metrics-row" id="metricsCards"></div>

<div class="chart-container">
<div class="chart-box"><div class="chart-title">📈 股价走势 + 海龟通道 + 买卖信号</div><div class="chart-wrap" id="chart1"></div></div>
<div class="chart-box"><div class="chart-title">📊 ATR 平均真实波幅</div><div class="chart-wrap" id="chart2"></div></div>
<div class="chart-box"><div class="chart-title">💰 资金权益曲线</div><div class="chart-wrap" id="chart3"></div></div>
<div class="chart-box"><div class="chart-title">📉 回撤曲线</div><div class="chart-wrap" id="chart4"></div></div>
</div>

<div class="trades-table" id="tradesSection"><h3 style="margin-bottom:12px">📋 交易记录明细表</h3><table id="tradesTable"><thead><tr>
<th>序号</th><th>入场日期</th><th>出场日期</th><th>入场价格</th><th>出场价格</th>
<th>持仓数量</th><th>盈亏</th><th>收益率</th><th>退出类型</th><th>持仓天数</th>
</tr></thead><tbody id="tradesBody"></tbody></table></div>

<script>
const DATA = DATA_PLACEHOLDER;

// === 指标卡片 ===
const cards = [
  { label: '最终资产', value: '¥' + DATA.metrics.final_equity.toLocaleString(), cls: '' },
  { label: '总收益率', value: (DATA.metrics.total_return >= 0 ? '+' : '') + DATA.metrics.total_return + '%', cls: DATA.metrics.total_return >= 0 ? 'positive' : 'negative' },
  { label: '年化收益率', value: (DATA.metrics.annual_return >= 0 ? '+' : '') + DATA.metrics.annual_return + '%', cls: DATA.metrics.annual_return >= 0 ? 'positive' : 'negative' },
  { label: '最大回撤', value: DATA.metrics.max_drawdown.toFixed(2) + '%', cls: 'negative' },
  { label: '夏普比率', value: DATA.metrics.sharpe.toFixed(3), cls: DATA.metrics.sharpe >= 0 ? 'positive' : 'negative' },
  { label: '胜率', value: DATA.metrics.win_rate + '% (' + DATA.metrics.win_trades + '胜/' + DATA.metrics.loss_trades + '负)', cls: DATA.metrics.win_rate >= 40 ? 'positive' : '' },
  { label: '盈亏比', value: DATA.metrics.profit_factor ? DATA.metrics.profit_factor.toFixed(2) : '∞', cls: 'positive' },
  { label: '年化波动率', value: DATA.metrics.annual_volatility.toFixed(2) + '%', cls: '' },
  { label: '买入持有', value: (DATA.metrics.buy_hold_return >= 0 ? '+' : '') + DATA.metrics.buy_hold_return + '%', cls: DATA.metrics.buy_hold_return >= 0 ? 'positive' : 'negative' },
  { label: '总交易次数', value: DATA.metrics.total_trades, cls: '' },
];
const container = document.getElementById('metricsCards');
cards.forEach(c => {
  const div = document.createElement('div'); div.className = 'metric-card';
  div.innerHTML = '<div class="label">' + c.label + '</div><div class="value ' + c.cls + '">' + c.value + '</div>';
  container.appendChild(div);
});

// === 图表1: 股价 + 通道 + 信号 ===
const fig1 = document.getElementById('chart1');
const trace1_price = { x: DATA.dates, y: DATA.close, type: 'scatter', mode: 'lines', name: '收盘价', line: { color: '#2c3e50', width: 1.5 } };
const trace1_upper = { x: DATA.dates, y: DATA.upper_channel, type: 'scatter', mode: 'lines', name: '上轨(' + 20 + ')', line: { color: '#e74c3c', width: 1, dash: 'dash' } };
const trace1_lower = { x: DATA.dates, y: DATA.lower_channel, type: 'scatter', mode: 'lines', name: '下轨(' + 20 + ')', line: { color: '#27ae60', width: 1, dash: 'dash' } };
const trace1_mid = { x: DATA.dates, y: DATA.middle_channel, type: 'scatter', mode: 'lines', name: '中轨', line: { color: '#95a5a6', width: 0.8, dash: 'dot' } };
const buyDates = [], buyPrices = [];
DATA.buy_signals.forEach((d,i) => { buyDates.push(d); buyPrices.push(DATA.buy_prices[i]); });
const trace1_buy = { x: buyDates, y: buyPrices, type: 'scatter', mode: 'markers', name: '买入', marker: { color: '#e74c3c', size: 10, symbol: 'triangle-up' } };
const sellDates = [], sellPrices = [];
DATA.sell_signals.forEach((d,i) => { sellDates.push(d); sellPrices.push(DATA.sell_prices[i]); });
const trace1_sell = { x: sellDates, y: sellPrices, type: 'scatter', mode: 'markers', name: '卖出', marker: { color: '#27ae60', size: 10, symbol: 'triangle-down' } };
Plotly.newPlot(fig1, [trace1_price, trace1_upper, trace1_lower, trace1_mid, trace1_buy, trace1_sell], {
  margin: { t: 10, r: 30, b: 50, l: 60 }, height: 500,
  xaxis: { rangeslider: { visible: true } }, hovermode: 'x unified',
  legend: { orientation: 'h', y: 1.02 }, template: { layout: { paper_bgcolor: 'white', plot_bgcolor: '#fafbfc' } }
}, { responsive: true, scrollZoom: true, displayModeBar: true, modeBarButtonsToAdd: ['drawline', 'eraseshape'] });

// === 图表2: ATR ===
const fig2 = document.getElementById('chart2');
Plotly.newPlot(fig2, [
  { x: DATA.dates, y: DATA.atr, type: 'scatter', mode: 'lines', name: 'ATR', line: { color: '#3498db', width: 1.5 }, fill: 'tozeroy', fillcolor: 'rgba(52,152,219,0.15)' }
], {
  margin: { t: 10, r: 30, b: 50, l: 60 }, height: 300,
  xaxis: { rangeslider: { visible: true } }, hovermode: 'x unified',
  template: { layout: { paper_bgcolor: 'white', plot_bgcolor: '#fafbfc' } }
}, { responsive: true, scrollZoom: true });

// === 图表3: 权益曲线 ===
const fig3 = document.getElementById('chart3');
const trace3_strategy = { x: DATA.equity_dates, y: DATA.equity, type: 'scatter', mode: 'lines', name: '策略权益', line: { color: '#e74c3c', width: 2 } };
const initialE = DATA.metrics.initial_capital;
const bhValues = DATA.close.map(c => initialE * c / DATA.close[0]);
const trace3_bh = { x: DATA.dates, y: bhValues, type: 'scatter', mode: 'lines', name: '买入持有', line: { color: '#95a5a6', width: 1.2, dash: 'dash' } };
Plotly.newPlot(fig3, [trace3_strategy, trace3_bh], {
  margin: { t: 10, r: 30, b: 50, l: 60 }, height: 350,
  xaxis: { rangeslider: { visible: true } }, hovermode: 'x unified',
  legend: { orientation: 'h', y: 1.02 },
  template: { layout: { paper_bgcolor: 'white', plot_bgcolor: '#fafbfc' } }
}, { responsive: true, scrollZoom: true });

// === 图表4: 回撤 ===
const fig4 = document.getElementById('chart4');
Plotly.newPlot(fig4, [
  { x: DATA.equity_dates, y: DATA.drawdown, type: 'scatter', mode: 'lines', name: '回撤', line: { color: '#e74c3c', width: 1.5 }, fill: 'tozeroy', fillcolor: 'rgba(231,76,60,0.15)' }
], {
  margin: { t: 10, r: 30, b: 50, l: 60 }, height: 250,
  xaxis: { rangeslider: { visible: true } }, hovermode: 'x unified',
  yaxis: { tickformat: '.1f', ticksuffix: '%' },
  template: { layout: { paper_bgcolor: 'white', plot_bgcolor: '#fafbfc' } }
}, { responsive: true, scrollZoom: true });

// === 交易记录表 ===
const tbody = document.getElementById('tradesBody');
DATA.trades.forEach((t, idx) => {
  const tr = document.createElement('tr');
  const pnlCls = t.pnl >= 0 ? 'trade-win' : 'trade-loss';
  const entryDate = typeof t.entry_date === 'string' ? t.entry_date : (t.entry_date && t.entry_date.$date ? t.entry_date.$date : '-');
  const exitDate = typeof t.exit_date === 'string' ? t.exit_date : (t.exit_date && t.exit_date.$date ? t.exit_date.$date : '-');
  tr.innerHTML = '<td>' + (idx+1) + '</td><td>' + entryDate + '</td><td>' + exitDate + '</td><td>' + t.entry_price.toFixed(2) + '</td><td>' + t.exit_price.toFixed(2) + '</td><td>' + t.position + '</td><td class="' + pnlCls + '">' + t.pnl.toFixed(2) + '</td><td class="' + pnlCls + '">' + (t.return_pct >= 0 ? '+' : '') + t.return_pct.toFixed(2) + '%</td><td>' + t.exit_type + '</td><td>' + t.hold_days + '</td>';
  tbody.appendChild(tr);
});
</script>
</body>
</html>'''

# 注入数据
html_output = html_template.replace('DATA_PLACEHOLDER', data_json).replace('{stock_code}', metrics['stock_code']).replace('{stock_name}', metrics['stock_name']).replace('{data_range}', metrics['data_range']).replace('{last_update}', metrics['last_update'])

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(html_output)

file_size = os.path.getsize(OUTPUT_FILE) / 1024
print(f"\n✅ HTML 看板已保存: {OUTPUT_FILE} ({file_size:.1f} KB)")
print(f"  数据日期: {metrics['data_range']}")
print(f"  更新日期: {metrics['last_update']}")
print(f"   总收益率: {metrics['total_return']}%")
print(f"   夏普比率: {metrics['sharpe']}")
print(f"   交易次数: {metrics['total_trades']}")

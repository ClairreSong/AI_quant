#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中芯国际 K线交易量看板生成脚本
- 通过 Tushare API 获取 688981.SH (A股) 和 00981.HK (港股) 近一年日线数据
- 保存 CSV
- 生成 HTML 看板 (ECharts K线 + 交易量)
"""

import json
import csv
import urllib.request
import os
import sys
from datetime import datetime

TOKEN = "bf565a2e89b3b2f8df37d2856fc20b65374d52e579170b719384b152"
API_URL = "https://api.tushare.pro"
START_DATE = "20250704"
END_DATE = "20260704"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(OUTPUT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_tushare(api_name, params):
    """Call Tushare REST API directly."""
    payload = json.dumps({
        "api_name": api_name,
        "token": TOKEN,
        "params": params,
        "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("code") != 0:
        raise RuntimeError(f"Tushare API error: {result.get('msg', 'unknown')}")
    return result["data"]


def save_csv(data, filepath):
    """Save Tushare data to CSV."""
    fields = data["fields"]
    rows = data["items"]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for row in rows:
            writer.writerow(row)
    print(f"  CSV saved: {filepath} ({len(rows)} rows)")


def build_chart_data(data):
    """Convert Tushare data to chart-ready arrays (oldest first)."""
    fields = data["fields"]
    rows = data["items"]
    idx = {name: i for i, name in enumerate(fields)}

    records = []
    for row in rows:
        records.append({
            "date": row[idx["trade_date"]],
            "open": row[idx["open"]],
            "close": row[idx["close"]],
            "low": row[idx["low"]],
            "high": row[idx["high"]],
            "vol": row[idx["vol"]],
            "amount": row[idx["amount"]],
            "pct_chg": row[idx["pct_chg"]],
        })
    # Sort by date ascending
    records.sort(key=lambda x: x["date"])

    # Format dates as YYYY-MM-DD
    for r in records:
        d = r["date"]
        r["date"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    return records


def generate_html(a_data, hk_data):
    """Generate self-contained HTML dashboard with ECharts."""
    a_records = build_chart_data(a_data)
    hk_records = build_chart_data(hk_data)

    a_json = json.dumps(a_records, ensure_ascii=False)
    hk_json = json.dumps(hk_records, ensure_ascii=False)

    # Compute summary stats
    def stats(records):
        latest = records[-1]
        first = records[0]
        year_high = max(r["high"] for r in records)
        year_low = min(r["low"] for r in records)
        avg_vol = sum(r["vol"] for r in records) / len(records)
        total_return = (latest["close"] - first["open"]) / first["open"] * 100
        return {
            "latest_close": latest["close"],
            "latest_date": latest["date"],
            "latest_pct": latest["pct_chg"],
            "year_high": year_high,
            "year_low": year_low,
            "avg_vol": avg_vol,
            "total_return": total_return,
        }

    a_stats = stats(a_records)
    hk_stats = stats(hk_records)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中芯国际 K线交易量看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Microsoft YaHei", "Segoe UI", sans-serif;
    background: #f5f7fa;
    color: #333;
    padding: 20px;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; }}

  /* Header */
  .header {{
    background: linear-gradient(135deg, #1a2332 0%, #2d3e50 100%);
    color: #fff;
    padding: 24px 32px;
    border-radius: 12px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .header h1 {{ font-size: 24px; font-weight: 600; }}
  .header .subtitle {{ font-size: 13px; opacity: 0.7; margin-top: 4px; }}
  .header .date-range {{
    background: rgba(255,255,255,0.15);
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px;
  }}

  /* Tabs */
  .tabs {{
    display: flex;
    gap: 0;
    margin-bottom: 16px;
    background: #fff;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}
  .tab {{
    flex: 1;
    padding: 14px 24px;
    text-align: center;
    cursor: pointer;
    font-size: 15px;
    font-weight: 500;
    color: #666;
    transition: all 0.3s;
    border-bottom: 3px solid transparent;
    user-select: none;
  }}
  .tab.active {{
    color: #e74c3c;
    border-bottom-color: #e74c3c;
    background: #fdf2f2;
  }}
  .tab:hover:not(.active) {{ background: #f8f9fa; }}
  .tab .code {{ font-size: 12px; color: #999; margin-top: 2px; }}

  /* Stats cards */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }}
  .stat-card {{
    background: #fff;
    padding: 16px 20px;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}
  .stat-card .label {{ font-size: 12px; color: #888; margin-bottom: 6px; }}
  .stat-card .value {{ font-size: 22px; font-weight: 700; }}
  .stat-card .sub {{ font-size: 12px; margin-top: 4px; }}
  .up {{ color: #e74c3c; }}
  .down {{ color: #27ae60; }}

  /* Chart container */
  .chart-wrapper {{
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-bottom: 20px;
  }}
  .chart-wrapper h3 {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #333;
  }}
  #kline-chart {{ width: 100%; height: 480px; }}
  #volume-chart {{ width: 100%; height: 200px; }}

  /* Footer */
  .footer {{
    text-align: center;
    font-size: 12px;
    color: #aaa;
    padding: 16px 0;
  }}

  /* Loading */
  #loading {{
    text-align: center;
    padding: 60px;
    font-size: 16px;
    color: #999;
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <div>
      <h1>中芯国际 SMIC — K线交易量看板</h1>
      <div class="subtitle">数据来源：Tushare | A股: 688981.SH (科创板) | 港股: 00981.HK</div>
    </div>
    <div class="date-range">{a_records[0]['date']} ~ {a_records[-1]['date']}</div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <div class="tab active" onclick="switchMarket('a')">
      A股 · 中芯国际
      <div class="code">688981.SH 科创板</div>
    </div>
    <div class="tab" onclick="switchMarket('hk')">
      港股 · 中芯国际
      <div class="code">00981.HK 联交所</div>
    </div>
  </div>

  <!-- Stats -->
  <div class="stats-grid" id="stats-grid"></div>

  <!-- K-line chart -->
  <div class="chart-wrapper">
    <h3>K 线图</h3>
    <div id="kline-chart"></div>
  </div>

  <!-- Volume chart -->
  <div class="chart-wrapper">
    <h3>交易量</h3>
    <div id="volume-chart"></div>
  </div>

  <div class="footer">
    数据来源 Tushare Pro | 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')} | 仅供研究参考，不构成投资建议
  </div>
</div>

<script>
// ===== Data =====
const aData = {a_json};
const hkData = {hk_json};

const aStats = {{
  latest_close: {a_stats['latest_close']},
  latest_date: '{a_stats['latest_date']}',
  latest_pct: {a_stats['latest_pct']},
  year_high: {a_stats['year_high']},
  year_low: {a_stats['year_low']},
  avg_vol: {a_stats['avg_vol']:.2f},
  total_return: {a_stats['total_return']:.2f},
  vol_unit: '手',
  price_unit: 'CNY',
  vol_divisor: 10000,  // 手 -> 万手
  amount_divisor: 100000,
}};

const hkStats = {{
  latest_close: {hk_stats['latest_close']},
  latest_date: '{hk_stats['latest_date']}',
  latest_pct: {hk_stats['latest_pct']},
  year_high: {hk_stats['year_high']},
  year_low: {hk_stats['year_low']},
  avg_vol: {hk_stats['avg_vol']:.2f},
  total_return: {hk_stats['total_return']:.2f},
  vol_unit: '股',
  price_unit: 'HKD',
  vol_divisor: 1000000,  // 股 -> 百万股
  amount_divisor: 100000000,
}};

let currentMarket = 'a';
let klineChart = null;
let volChart = null;

// Chinese convention: red = up, green = down
const UP_COLOR = '#e74c3c';
const DOWN_COLOR = '#27ae60';
const UP_BORDER = '#c0392b';
const DOWN_BORDER = '#1e8449';

function getCurrentData() {{
  return currentMarket === 'a' ? aData : hkData;
}}

function getCurrentStats() {{
  return currentMarket === 'a' ? aStats : hkStats;
}}

function renderStats() {{
  const s = getCurrentStats();
  const pctClass = s.latest_pct >= 0 ? 'up' : 'down';
  const retClass = s.total_return >= 0 ? 'up' : 'down';
  const volDisplay = (s.avg_vol / s.vol_divisor).toFixed(2);

  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card">
      <div class="label">最新收盘价 (${{s.price_unit}})</div>
      <div class="value ${{pctClass}}">${{s.latest_close.toFixed(2)}}</div>
      <div class="sub ${{pctClass}}">${{s.latest_date}} ${{s.latest_pct >= 0 ? '+' : ''}}${{s.latest_pct.toFixed(2)}}%</div>
    </div>
    <div class="stat-card">
      <div class="label">年内最高 (${{s.price_unit}})</div>
      <div class="value up">${{s.year_high.toFixed(2)}}</div>
    </div>
    <div class="stat-card">
      <div class="label">年内最低 (${{s.price_unit}})</div>
      <div class="value down">${{s.year_low.toFixed(2)}}</div>
    </div>
    <div class="stat-card">
      <div class="label">日均成交量 (${{currentMarket === 'a' ? '万手' : '百万股'}})</div>
      <div class="value">${{volDisplay}}</div>
    </div>
    <div class="stat-card">
      <div class="label">区间涨跌幅</div>
      <div class="value ${{retClass}}">${{s.total_return >= 0 ? '+' : ''}}${{s.total_return.toFixed(2)}}%</div>
    </div>
    <div class="stat-card">
      <div class="label">振幅</div>
      <div class="value">${{((s.year_high - s.year_low) / s.year_low * 100).toFixed(1)}}%</div>
    </div>
  `;
}}

function renderKline() {{
  const data = getCurrentData();
  const dates = data.map(d => d.date);
  const ohlc = data.map(d => [d.open, d.close, d.low, d.high]);

  const option = {{
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {{
      trigger: 'axis',
      axisPointer: {{ type: 'cross' }},
      formatter: function(params) {{
        const p = params[0];
        const idx = p.dataIndex;
        const d = data[idx];
        const changeClass = d.close >= d.open ? 'color:#e74c3c' : 'color:#27ae60';
        return `<div style="font-size:13px;line-height:1.8">
          <b>${{d.date}}</b><br/>
          <span>开盘: ${{d.open.toFixed(2)}}</span><br/>
          <span>收盘: <b style="${{changeClass}}">${{d.close.toFixed(2)}}</b></span><br/>
          <span>最高: <span style="color:#e74c3c">${{d.high.toFixed(2)}}</span></span><br/>
          <span>最低: <span style="color:#27ae60">${{d.low.toFixed(2)}}</span></span><br/>
          <span>涨跌幅: <b style="${{d.pct_chg >= 0 ? 'color:#e74c3c' : 'color:#27ae60'}}">${{d.pct_chg >= 0 ? '+' : ''}}${{d.pct_chg.toFixed(2)}}%</b></span><br/>
          <span>成交量: ${{(d.vol / getCurrentStats().vol_divisor).toFixed(2)}} ${{currentMarket === 'a' ? '万手' : '百万股'}}</span>
        </div>`;
      }}
    }},
    axisPointer: {{ link: [{{ xAxisIndex: 'all' }}] }},
    grid: [
      {{ left: '8%', right: '4%', top: '6%', height: '62%' }},
      {{ left: '8%', right: '4%', top: '78%', height: '16%' }}
    ],
    xAxis: [
      {{
        type: 'category',
        data: dates,
        scale: true,
        boundaryGap: false,
        splitLine: {{ show: false }},
        axisLabel: {{ show: false }}
      }},
      {{
        type: 'category',
        gridIndex: 1,
        data: dates,
        scale: true,
        boundaryGap: false,
        splitLine: {{ show: false }},
        axisLabel: {{ fontSize: 10, color: '#999' }}
      }}
    ],
    yAxis: [
      {{
        scale: true,
        splitLine: {{ lineStyle: {{ type: 'dashed', color: '#eee' }} }},
        axisLabel: {{ fontSize: 11, color: '#666' }}
      }},
      {{
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: {{ show: false }},
        splitLine: {{ show: false }}
      }}
    ],
    dataZoom: [
      {{
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 0,
        end: 100
      }},
      {{
        show: true,
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: '2%',
        height: 20,
        start: 0,
        end: 100,
        borderColor: '#ddd',
        fillerColor: 'rgba(200,200,200,0.15)',
        handleStyle: {{ color: '#999' }}
      }}
    ],
    series: [
      {{
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {{
          color: UP_COLOR,
          color0: DOWN_COLOR,
          borderColor: UP_BORDER,
          borderColor0: DOWN_BORDER
        }},
        markLine: {{
          symbol: ['none', 'none'],
          label: {{ fontSize: 10 }},
          lineStyle: {{ type: 'dashed', width: 1 }},
          data: [
            {{ type: 'max', name: '年内最高', valueIndex: 3, itemStyle: {{ color: '#e74c3c' }} }},
            {{ type: 'min', name: '年内最低', valueIndex: 2, itemStyle: {{ color: '#27ae60' }} }},
          ]
        }}
      }}
    ]
  }};

  klineChart.setOption(option, true);
}}

function renderVolume() {{
  const data = getCurrentData();
  const s = getCurrentStats();
  const dates = data.map(d => d.date);
  const vols = data.map(d => {{
    const v = d.vol / s.vol_divisor;
    const isUp = d.close >= d.open;
    return {{
      value: v,
      itemStyle: {{ color: isUp ? UP_COLOR : DOWN_COLOR }}
    }};
  }});

  const option = {{
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {{
      trigger: 'axis',
      formatter: function(params) {{
        const p = params[0];
        const idx = p.dataIndex;
        const d = data[idx];
        return `<div style="font-size:13px">
          <b>${{d.date}}</b><br/>
          成交量: ${{p.value.toFixed(2)}} ${{currentMarket === 'a' ? '万手' : '百万股'}}<br/>
          成交额: ${{(d.amount / s.amount_divisor).toFixed(2)}} ${{currentMarket === 'a' ? '亿元' : '亿港元'}}
        </div>`;
      }}
    }},
    grid: {{ left: '8%', right: '4%', top: '10%', height: '70%' }},
    xAxis: {{
      type: 'category',
      data: dates,
      axisLabel: {{ fontSize: 10, color: '#999' }}
    }},
    yAxis: {{
      axisLabel: {{ fontSize: 11, color: '#666' }},
      splitLine: {{ lineStyle: {{ type: 'dashed', color: '#eee' }} }}
    }},
    dataZoom: [
      {{ type: 'inside', start: 0, end: 100 }}
    ],
    series: [{{
      name: '成交量',
      type: 'bar',
      data: vols,
    }}]
  }};

  volChart.setOption(option, true);
}}

function switchMarket(market) {{
  currentMarket = market;
  document.querySelectorAll('.tab').forEach((t, i) => {{
    t.classList.toggle('active', (i === 0 && market === 'a') || (i === 1 && market === 'hk'));
  }});
  renderStats();
  renderKline();
  renderVolume();
}}

// Init
window.addEventListener('DOMContentLoaded', function() {{
  klineChart = echarts.init(document.getElementById('kline-chart'));
  volChart = echarts.init(document.getElementById('volume-chart'));
  renderStats();
  renderKline();
  renderVolume();
  window.addEventListener('resize', function() {{
    klineChart.resize();
    volChart.resize();
  }});
}});
</script>
</body>
</html>"""

    filepath = os.path.join(OUTPUT_DIR, "smic_dashboard.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML dashboard saved: {filepath}")


def fetch_with_cache(api_name, params, cache_filename):
    """Fetch from Tushare API with local JSON cache fallback."""
    cache_path = os.path.join(DATA_DIR, cache_filename)

    # Try API first
    try:
        data = fetch_tushare(api_name, params)
        # Save to cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"  Fetched from API, cached to {cache_filename}")
        return data
    except Exception as e:
        print(f"  API failed: {e}")
        # Try cache
        if os.path.exists(cache_path):
            print(f"  Loading from cache: {cache_filename}")
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            print(f"  No cache available for {cache_filename}")
            raise


def main():
    print("=" * 60)
    print("中芯国际 K线交易量看板生成")
    print("=" * 60)

    # 1. Fetch A-share data
    print("\n[1/4] Fetching A-share daily data (688981.SH)...")
    a_data = fetch_with_cache("daily", {
        "ts_code": "688981.SH",
        "start_date": START_DATE,
        "end_date": END_DATE
    }, "smic_688981_SH_raw.json")
    print(f"  Got {len(a_data['items'])} records")

    # 2. Fetch HK data
    print("\n[2/4] Fetching HK daily data (00981.HK)...")
    hk_data = fetch_with_cache("hk_daily", {
        "ts_code": "00981.HK",
        "start_date": START_DATE,
        "end_date": END_DATE
    }, "smic_00981_HK_raw.json")
    print(f"  Got {len(hk_data['items'])} records")

    # 3. Save CSV
    print("\n[3/4] Saving CSV files...")
    save_csv(a_data, os.path.join(DATA_DIR, "smic_688981_SH.csv"))
    save_csv(hk_data, os.path.join(DATA_DIR, "smic_00981_HK.csv"))

    # 4. Generate HTML
    print("\n[4/4] Generating HTML dashboard...")
    generate_html(a_data, hk_data)

    print("\n" + "=" * 60)
    print("Done! Output files:")
    print(f"  CSV:  data/smic_688981_SH.csv")
    print(f"  CSV:  data/smic_00981_HK.csv")
    print(f"  HTML: smic_dashboard.html")
    print("=" * 60)


if __name__ == "__main__":
    main()

import pandas as pd
from datetime import datetime
from typing import Dict, Optional
from analyzer import get_period_label


def fmt_delta(val, is_pct=False, is_rate=False):
    if val == "N/A":
        return '<span class="na">—</span>'
    v = val
    if v > 0:
        arrow = "▲"
        cls = "up"
    elif v < 0:
        arrow = "▼"
        cls = "down"
    else:
        arrow = "—"
        cls = "flat"
    if is_pct:
        return f'<span class="{cls}">{arrow} {v:+.1f}%</span>'
    if isinstance(v, float):
        return f'<span class="{cls}">{arrow} {v:+.2f}</span>'
    return f'<span class="{cls}">{arrow} {v:+d}</span>'


def metric_card(title, current, previous, delta_pct, is_rate=False, suffix=""):
    if is_rate:
        curr_str = f"{current:.1%}"
        prev_str = f"{previous:.1%}" if previous else "—"
    elif isinstance(current, float):
        curr_str = f"{current:.2f}"
        prev_str = f"{previous:.2f}" if previous else "—"
    else:
        curr_str = f"{current}{suffix}"
        prev_str = f"{previous}{suffix}" if previous else "—"

    delta_html = fmt_delta(delta_pct if isinstance(delta_pct, (int, float)) else 0, is_pct=True)
    if delta_pct == "N/A":
        delta_html = '<span class="na">上期无数据</span>'

    return f"""
    <div class="metric-card">
      <div class="metric-title">{title}</div>
      <div class="metric-value">{curr_str}</div>
      <div class="metric-compare">上期: {prev_str} {delta_html}</div>
    </div>
    """


def generate_html_report(
    period_type: str,
    current_period: str,
    comparison: Dict,
    period_summary: pd.DataFrame,
    act_metrics: pd.DataFrame,
    followup: pd.DataFrame,
    filters_info: str = "",
) -> str:
    meta = comparison.get("_meta", {})
    curr_label = meta.get("current_label", current_period)
    prev_label = meta.get("previous_label", "")
    report_title = "志愿服务周报" if period_type == "weekly" else "志愿服务月报"
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cards_html = ""
    metric_defs = [
        ("活动数量", "activity_count", False, ""),
        ("报名总人次", "total_registrations", False, ""),
        ("签到总人次", "total_signins", False, ""),
        ("平均签到率", "avg_signin_rate", True, ""),
        ("任务完成率", "avg_completion_rate", True, ""),
        ("平均反馈评分", "avg_score", False, ""),
        ("风险活动数", "risk_activity_count", False, ""),
        ("待跟进任务", "total_pending_tasks", False, ""),
    ]
    for title, key, is_rate, suffix in metric_defs:
        d = comparison.get(key, {})
        cards_html += metric_card(
            title,
            d.get("current", 0),
            d.get("previous", 0),
            d.get("delta_pct", 0),
            is_rate=is_rate,
            suffix=suffix,
        )

    act_table_html = ""
    if len(act_metrics) > 0:
        act_table_html = """
        <table>
          <thead>
            <tr>
              <th>活动ID</th><th>活动名称</th><th>日期</th><th>负责人</th>
              <th>报名</th><th>签到</th><th>签到率</th>
              <th>任务完成率</th><th>平均评分</th><th>风险标记</th>
            </tr>
          </thead>
          <tbody>
        """
        for _, row in act_metrics.sort_values("date").iterrows():
            risk_cls = ' class="risk-row"' if row.get("has_risk", False) else ""
            score_str = f"{row['avg_score']:.2f}" if row['avg_score'] > 0 else "—"
            act_table_html += f"""
            <tr{risk_cls}>
              <td>{row['activity_id']}</td>
              <td>{row['name']}</td>
              <td>{pd.Timestamp(row['date']).strftime('%Y-%m-%d')}</td>
              <td>{row['person_in_charge']}</td>
              <td>{row['reg_count']}</td>
              <td>{row['signin_count']}</td>
              <td>{row['signin_rate']:.0%}</td>
              <td>{row['task_completion_rate']:.0%}</td>
              <td>{score_str}</td>
              <td>{row.get('risk_flags', '') or '正常'}</td>
            </tr>
            """
        act_table_html += "</tbody></table>"
    else:
        act_table_html = "<p>本期无活动数据。</p>"

    fu_table_html = ""
    if len(followup) > 0:
        fu_table_html = """
        <table>
          <thead>
            <tr><th>优先级</th><th>活动</th><th>负责人</th><th>类型</th><th>详情</th></tr>
          </thead>
          <tbody>
        """
        pri_cls_map = {"高": "prio-high", "中": "prio-mid", "低": "prio-low"}
        for _, row in followup.iterrows():
            pcls = pri_cls_map.get(row["priority"], "")
            fu_table_html += f"""
            <tr>
              <td class="{pcls}">{row['priority']}</td>
              <td>{row['activity_name']} ({row['activity_id']})</td>
              <td>{row['person_in_charge']}</td>
              <td>{row['type']}</td>
              <td>{row['detail']}</td>
            </tr>
            """
        fu_table_html += "</tbody></table>"
    else:
        fu_table_html = "<p>暂无待跟进事项 ✅</p>"

    trend_html = ""
    if len(period_summary) > 0:
        trend_html = """
        <table>
          <thead><tr><th>周期</th><th>活动数</th><th>报名</th><th>签到率</th><th>完成率</th><th>评分</th><th>风险数</th></tr></thead>
          <tbody>
        """
        for _, row in period_summary.sort_values("period_start").iterrows():
            is_curr = ' class="current-row"' if row["period"] == current_period else ""
            label = get_period_label(row["period"], period_type)
            score_str = f"{row['avg_score']:.2f}" if row['avg_score'] > 0 else "—"
            trend_html += f"""
            <tr{is_curr}>
              <td>{label}</td>
              <td>{row['activity_count']}</td>
              <td>{row['total_registrations']}</td>
              <td>{row['avg_signin_rate']:.0%}</td>
              <td>{row['avg_completion_rate']:.0%}</td>
              <td>{score_str}</td>
              <td>{row['risk_activity_count']}</td>
            </tr>
            """
        trend_html += "</tbody></table>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{report_title} - {curr_label}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #f5f7fa; color: #2c3e50; padding: 24px; line-height: 1.6; }}
  .container {{ max-width: 1100px; margin: 0 auto; background: #fff; border-radius: 12px;
               box-shadow: 0 2px 12px rgba(0,0,0,0.06); padding: 32px; }}
  h1 {{ font-size: 24px; color: #1a73e8; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; border-bottom: 2px solid #e8f0fe; padding-bottom: 16px; }}
  h2 {{ font-size: 18px; color: #1a73e8; margin: 24px 0 12px; padding-left: 10px; border-left: 4px solid #1a73e8; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .metric-card {{ background: linear-gradient(135deg, #f8faff, #e8f0fe); border-radius: 10px; padding: 16px; border: 1px solid #d2e3fc; }}
  .metric-title {{ font-size: 13px; color: #5f6368; margin-bottom: 6px; }}
  .metric-value {{ font-size: 28px; font-weight: 700; color: #1a73e8; }}
  .metric-compare {{ font-size: 12px; color: #80868b; margin-top: 4px; }}
  .up {{ color: #0d904f; font-weight: 600; }}
  .down {{ color: #d93025; font-weight: 600; }}
  .flat {{ color: #80868b; }}
  .na {{ color: #bbb; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 13px; }}
  th {{ background: #f1f3f4; padding: 10px 8px; text-align: left; font-weight: 600; color: #3c4043; border-bottom: 2px solid #dadce0; }}
  td {{ padding: 9px 8px; border-bottom: 1px solid #f1f3f4; }}
  tr:hover {{ background: #f8faff; }}
  .risk-row {{ background: #fce8e6; }}
  .risk-row:hover {{ background: #fadbd8; }}
  .current-row {{ background: #e8f0fe; font-weight: 600; }}
  .prio-high {{ color: #d93025; font-weight: 700; }}
  .prio-mid {{ color: #f9ab00; font-weight: 600; }}
  .prio-low {{ color: #34a853; }}
  .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center; }}
  .filter-info {{ background: #fff8e1; border-left: 4px solid #f9ab00; padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; font-size: 13px; }}
</style>
</head>
<body>
<div class="container">
  <h1>{report_title}</h1>
  <div class="subtitle">
    报告周期：<strong>{curr_label}</strong> &nbsp;|&nbsp;
    对比周期：{prev_label} &nbsp;|&nbsp;
    生成时间：{gen_time}
  </div>
  {f'<div class="filter-info">{filters_info}</div>' if filters_info else ''}

  <h2>📊 核心指标概览</h2>
  <div class="metrics-grid">
    {cards_html}
  </div>

  <h2>📈 周期趋势对比</h2>
  {trend_html}

  <h2>📋 本期活动明细</h2>
  {act_table_html}

  <h2>⚠️ 待跟进清单</h2>
  {fu_table_html}

  <div class="footer">
    志愿服务管理报表系统 · 自动生成 · {gen_time}
  </div>
</div>
</body>
</html>"""
    return html


def df_to_csv_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def build_export_tables(act_metrics, period_summary, comparison, followup, period_type, current_period):
    meta = comparison.get("_meta", {})
    label = meta.get("current_label", current_period)

    overview_rows = []
    name_map = {
        "activity_count": "活动数量",
        "total_registrations": "报名总人次",
        "total_signins": "签到总人次",
        "avg_signin_rate": "平均签到率",
        "avg_completion_rate": "平均任务完成率",
        "avg_score": "平均反馈评分",
        "risk_activity_count": "风险活动数",
        "total_pending_tasks": "待跟进任务数",
    }
    for key, label_cn in name_map.items():
        d = comparison.get(key, {})
        overview_rows.append({
            "指标": label_cn,
            "本期值": d.get("current", 0),
            "上期值": d.get("previous", 0),
            "环比变化": d.get("delta", 0),
            "环比百分比": f"{d.get('delta_pct', 0)}%" if isinstance(d.get("delta_pct"), (int, float)) else "N/A",
        })
    overview_df = pd.DataFrame(overview_rows)

    act_export = act_metrics[["activity_id", "name", "date", "person_in_charge", "location",
                               "reg_count", "signin_count", "signin_rate",
                               "task_total", "task_completed", "task_completion_rate",
                               "avg_score", "fb_count", "risk_flags"]].copy()
    act_export.columns = ["活动ID", "活动名称", "日期", "负责人", "地点",
                           "报名人数", "签到人数", "签到率",
                           "任务总数", "已完成任务", "任务完成率",
                           "平均评分", "反馈数量", "风险标记"]
    for c in ["签到率", "任务完成率"]:
        act_export[c] = act_export[c].apply(lambda x: f"{x:.0%}")
    act_export["平均评分"] = act_export["平均评分"].apply(lambda x: f"{x:.2f}" if x > 0 else "")
    act_export["日期"] = act_export["日期"].apply(lambda x: pd.Timestamp(x).strftime("%Y-%m-%d"))

    fu_export = followup.rename(columns={
        "activity_id": "活动ID", "activity_name": "活动名称",
        "person_in_charge": "负责人", "type": "类型",
        "detail": "详情", "priority": "优先级",
    }) if len(followup) > 0 else followup

    trend_export = period_summary[["period", "activity_count", "total_registrations", "total_signins",
                                    "avg_signin_rate", "avg_completion_rate", "avg_score",
                                    "risk_activity_count", "total_pending_tasks"]].copy()
    from analyzer import get_period_label
    trend_export.insert(0, "周期名称", trend_export["period"].apply(lambda p: get_period_label(p, period_type)))
    trend_export.columns = ["周期名称", "周期键", "活动数", "报名人次", "签到人次",
                              "平均签到率", "平均完成率", "平均评分", "风险活动数", "待跟进任务数"]
    for c in ["平均签到率", "平均完成率"]:
        trend_export[c] = trend_export[c].apply(lambda x: f"{x:.0%}")

    return overview_df, act_export, fu_export, trend_export

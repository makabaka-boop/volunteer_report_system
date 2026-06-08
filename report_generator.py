import pandas as pd
from data_processor import (
    build_period_report,
    compute_checkin_rate,
    compute_task_completion_rate,
    compute_avg_feedback,
    compute_registration_count,
    assign_period,
    _overlap_filter,
)
from risk_analyzer import analyze_risks, build_followup_list


def generate_html_report(activities, checkins, tasks, feedbacks, mode, date_range=None):
    report_df, trends = build_period_report(activities, checkins, tasks, feedbacks, mode, date_range)

    if report_df.empty:
        return "<p>无数据可生成报告。</p>", pd.DataFrame(), [], pd.DataFrame(), pd.DataFrame()

    mode_label = "周报" if mode == "week" else "月报"

    act_with_period = assign_period(activities, mode)
    act_with_period = _overlap_filter(act_with_period, date_range)

    detail_rows = []
    for _, act_row in act_with_period.iterrows():
        aid = act_row["activity_id"]
        reg = 0
        cr = 0.0
        tr = 0.0
        avg_s = 0.0

        if not checkins.empty:
            c = checkins[checkins["activity_id"] == aid]
            reg = c["volunteer_name"].nunique()
            checked = c[c["status"] == "已签到"]["volunteer_name"].nunique()
            cr = round(checked / reg * 100, 1) if reg > 0 else 0.0

        if not tasks.empty:
            t = tasks[tasks["activity_id"] == aid]
            t_total = len(t)
            t_done = len(t[t["completion_status"] == "已完成"])
            tr = round(t_done / t_total * 100, 1) if t_total > 0 else 0.0

        if not feedbacks.empty:
            f = feedbacks[feedbacks["activity_id"] == aid]
            avg_s = round(f["score"].mean(), 2) if not f.empty else 0.0

        detail_rows.append({
            "周期": act_row["period_label"],
            "活动ID": aid,
            "活动名称": act_row["activity_name"],
            "负责人": act_row["responsible_person"],
            "开始日期": str(act_row["start_date"].date()) if pd.notna(act_row["start_date"]) else "",
            "结束日期": str(act_row["end_date"].date()) if pd.notna(act_row["end_date"]) else "",
            "报名人数": reg,
            "签到率(%)": cr,
            "任务完成率(%)": tr,
            "平均反馈评分": avg_s,
        })

    detail_df = pd.DataFrame(detail_rows)

    risk_df = analyze_risks(act_with_period, checkins, tasks, feedbacks)
    followup_df = build_followup_list(act_with_period, checkins, tasks)

    html = _build_html(mode_label, report_df, trends, detail_df, risk_df, followup_df)
    return html, detail_df, trends, risk_df, followup_df


def _build_html(mode_label, report_df, trends, detail_df, risk_df, followup_df):
    rows_html = ""
    for _, r in report_df.iterrows():
        rows_html += f"""
        <tr>
            <td>{r['周期']}</td>
            <td>{r['活动数']}</td>
            <td>{r['报名人数']}</td>
            <td>{r['签到率(%)']}</td>
            <td>{r['任务完成率(%)']}</td>
            <td>{r['平均反馈评分']}</td>
        </tr>"""

    trend_html = ""
    for t in trends:
        trend_html += f"""
        <tr>
            <td>{t['周期']}</td>
            <td>{_fmt_change(t['报名人数变化'])}</td>
            <td>{_fmt_change(t['签到率变化(%)'])}</td>
            <td>{_fmt_change(t['任务完成率变化(%)'])}</td>
            <td>{_fmt_change(t['评分变化'])}</td>
        </tr>"""

    detail_html = ""
    for _, d in detail_df.iterrows():
        detail_html += f"""
        <tr>
            <td>{d['周期']}</td>
            <td>{d['活动名称']}</td>
            <td>{d['负责人']}</td>
            <td>{d['开始日期']}</td>
            <td>{d['报名人数']}</td>
            <td>{d['签到率(%)']}</td>
            <td>{d['任务完成率(%)']}</td>
            <td>{d['平均反馈评分']}</td>
        </tr>"""

    risk_html = ""
    if risk_df.empty:
        risk_html = '<tr><td colspan="6" style="text-align:center;color:#34a853;">当前无风险项</td></tr>'
    else:
        for _, r in risk_df.iterrows():
            risk_html += f"""
            <tr>
                <td>{r['活动ID']}</td>
                <td>{r['活动名称']}</td>
                <td>{r['负责人']}</td>
                <td>{r['风险类型']}</td>
                <td>{r['当前值']}</td>
                <td>{r['阈值']}</td>
                <td>{r['建议']}</td>
            </tr>"""

    followup_html = ""
    if followup_df.empty:
        followup_html = '<tr><td colspan="5" style="text-align:center;color:#34a853;">当前无待跟进事项</td></tr>'
    else:
        for _, f in followup_df.iterrows():
            followup_html += f"""
            <tr>
                <td>{f['活动ID']}</td>
                <td>{f['活动名称']}</td>
                <td>{f['负责人']}</td>
                <td>{f['待跟进事项']}</td>
                <td>{f['类型']}</td>
            </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>志愿服务{mode_label}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #f8f9fa; color: #333; }}
h1 {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }}
h2 {{ color: #34a853; margin-top: 32px; }}
h2.risk {{ color: #ea4335; }}
h2.followup {{ color: #f9ab00; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th {{ background: #1a73e8; color: #fff; padding: 10px 12px; text-align: left; }}
th.risk-th {{ background: #ea4335; }}
th.followup-th {{ background: #f9ab00; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #e0e0e0; }}
tr:hover {{ background: #f1f3f4; }}
.positive {{ color: #34a853; font-weight: bold; }}
.negative {{ color: #ea4335; font-weight: bold; }}
</style>
</head>
<body>
<h1>志愿服务{mode_label}</h1>

<h2>周期汇总</h2>
<table>
<thead><tr><th>周期</th><th>活动数</th><th>报名人数</th><th>签到率(%)</th><th>任务完成率(%)</th><th>平均反馈评分</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>

<h2>环比变化</h2>
<table>
<thead><tr><th>周期</th><th>报名人数变化</th><th>签到率变化(%)</th><th>任务完成率变化(%)</th><th>评分变化</th></tr></thead>
<tbody>{trend_html}</tbody>
</table>

<h2>活动明细</h2>
<table>
<thead><tr><th>周期</th><th>活动名称</th><th>负责人</th><th>开始日期</th><th>报名人数</th><th>签到率(%)</th><th>任务完成率(%)</th><th>平均反馈评分</th></tr></thead>
<tbody>{detail_html}</tbody>
</table>

<h2 class="risk">风险提醒</h2>
<table>
<thead><tr><th class="risk-th">活动ID</th><th class="risk-th">活动名称</th><th class="risk-th">负责人</th><th class="risk-th">风险类型</th><th class="risk-th">当前值</th><th class="risk-th">阈值</th><th class="risk-th">建议</th></tr></thead>
<tbody>{risk_html}</tbody>
</table>

<h2 class="followup">待跟进清单</h2>
<table>
<thead><tr><th class="followup-th">活动ID</th><th class="followup-th">活动名称</th><th class="followup-th">负责人</th><th class="followup-th">待跟进事项</th><th class="followup-th">类型</th></tr></thead>
<tbody>{followup_html}</tbody>
</table>

</body>
</html>"""


def _fmt_change(val):
    if val > 0:
        return f'<span class="positive">+{val}</span>'
    elif val < 0:
        return f'<span class="negative">{val}</span>'
    return "0"

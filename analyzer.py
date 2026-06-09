import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


REQUIRED_COLUMNS = {
    "activities": ["activity_id", "name", "date", "person_in_charge", "location", "capacity"],
    "registrations": ["registration_id", "activity_id", "volunteer_id", "volunteer_name", "volunteer_phone", "register_time"],
    "signins": ["signin_id", "activity_id", "volunteer_id", "signin_time"],
    "tasks": ["task_id", "activity_id", "volunteer_id", "task_name", "status", "update_time"],
    "feedback": ["activity_id", "volunteer_id", "score", "feedback_time", "comment"],
}


def validate_and_parse(df: pd.DataFrame, name: str) -> pd.DataFrame:
    required = REQUIRED_COLUMNS.get(name, [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} 缺少必要列: {', '.join(missing)}")
    df = df.copy()
    date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
    for c in date_cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def assign_period(date_val, period_type: str) -> str:
    if pd.isna(date_val):
        return "未知"
    dt = pd.Timestamp(date_val)
    if period_type == "weekly":
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    else:
        return dt.strftime("%Y-%m")


def get_period_range(period_key: str, period_type: str) -> Tuple[datetime, datetime]:
    if period_type == "weekly":
        year, week = period_key.split("-W")
        year, week = int(year), int(week)
        start = datetime.fromisocalendar(year, week, 1)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return start, end
    else:
        year, month = period_key.split("-")
        year, month = int(year), int(month)
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(seconds=1)
        return start, end


def get_previous_period(period_key: str, period_type: str) -> Optional[str]:
    if period_key == "未知":
        return None
    if period_type == "weekly":
        year, week = period_key.split("-W")
        year, week = int(year), int(week)
        prev_date = datetime.fromisocalendar(year, week, 1) - timedelta(days=7)
        iso = prev_date.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    else:
        year, month = period_key.split("-")
        year, month = int(year), int(month)
        if month == 1:
            return f"{year - 1}-12"
        return f"{year}-{month - 1:02d}"


def get_period_label(period_key: str, period_type: str) -> str:
    if period_key == "未知":
        return "未知"
    start, end = get_period_range(period_key, period_type)
    if period_type == "weekly":
        return f"{start.strftime('%Y/%m/%d')} ~ {end.strftime('%m/%d')}"
    return f"{start.strftime('%Y年%m月')}"


def compute_activity_metrics(
    activities: pd.DataFrame,
    registrations: pd.DataFrame,
    signins: pd.DataFrame,
    tasks: pd.DataFrame,
    feedback: pd.DataFrame,
) -> pd.DataFrame:
    acts = activities.copy()

    reg_count = registrations.groupby("activity_id")["volunteer_id"].nunique().rename("reg_count")
    sin_count = signins.groupby("activity_id")["volunteer_id"].nunique().rename("signin_count")
    task_total = tasks.groupby("activity_id")["task_id"].count().rename("task_total")
    task_done = tasks[tasks["status"] == "completed"].groupby("activity_id")["task_id"].count().rename("task_completed")
    task_pending = tasks[tasks["status"].isin(["pending", "in_progress"])].groupby("activity_id")["task_id"].count().rename("task_pending")
    fb_stats = feedback.groupby("activity_id").agg(
        avg_score=("score", "mean"),
        fb_count=("score", "count"),
    )

    acts = acts.merge(reg_count, on="activity_id", how="left")
    acts = acts.merge(sin_count, on="activity_id", how="left")
    acts = acts.merge(task_total, on="activity_id", how="left")
    acts = acts.merge(task_done, on="activity_id", how="left")
    acts = acts.merge(task_pending, on="activity_id", how="left")
    acts = acts.merge(fb_stats, on="activity_id", how="left")

    for c in ["reg_count", "signin_count", "task_total", "task_completed", "task_pending", "fb_count"]:
        acts[c] = acts[c].fillna(0).astype(int)
    acts["avg_score"] = acts["avg_score"].fillna(0)

    acts["signin_rate"] = np.where(acts["reg_count"] > 0, acts["signin_count"] / acts["reg_count"], 0.0)
    acts["task_completion_rate"] = np.where(acts["task_total"] > 0, acts["task_completed"] / acts["task_total"], 0.0)

    risks = []
    for _, row in acts.iterrows():
        r = []
        if row["reg_count"] > 0 and row["signin_rate"] < 0.6:
            r.append(f"签到率偏低 ({row['signin_rate']:.0%})")
        if row["task_total"] > 0 and row["task_completion_rate"] < 0.7:
            r.append(f"任务完成率不足 ({row['task_completion_rate']:.0%})")
        if row["fb_count"] > 0 and row["avg_score"] < 3.0:
            r.append(f"反馈评分较低 ({row['avg_score']:.1f})")
        if row["task_pending"] > 0:
            r.append(f"待跟进任务 {row['task_pending']} 项")
        if row["fb_count"] == 0 and row["date"] < pd.Timestamp(datetime.now()):
            r.append("未收集到反馈")
        risks.append("；".join(r))
    acts["risk_flags"] = risks
    acts["has_risk"] = acts["risk_flags"].apply(lambda x: len(x) > 0)

    return acts


def build_period_summary(act_metrics: pd.DataFrame, period_type: str) -> pd.DataFrame:
    df = act_metrics.copy()
    df["period"] = df["date"].apply(lambda d: assign_period(d, period_type))
    df["period_start"] = df["date"].apply(lambda d: pd.Timestamp(d))
    df = df.sort_values("period_start")

    summary = df.groupby("period").agg(
        activity_count=("activity_id", "count"),
        total_registrations=("reg_count", "sum"),
        total_signins=("signin_count", "sum"),
        total_tasks=("task_total", "sum"),
        total_completed=("task_completed", "sum"),
        avg_signin_rate=("signin_rate", "mean"),
        avg_completion_rate=("task_completion_rate", "mean"),
        avg_score=("avg_score", "mean"),
        risk_activity_count=("has_risk", "sum"),
        total_pending_tasks=("task_pending", "sum"),
    ).reset_index()

    summary["period_start"] = summary["period"].apply(lambda p: get_period_range(p, period_type)[0])
    summary = summary.sort_values("period_start").reset_index(drop=True)

    for col in ["avg_signin_rate", "avg_completion_rate", "avg_score"]:
        summary[col] = summary[col].fillna(0)

    return summary


def compare_periods(summary: pd.DataFrame, current_period: str, period_type: str) -> Dict:
    prev_key = get_previous_period(current_period, period_type)
    curr_row = summary[summary["period"] == current_period]
    prev_row = summary[summary["period"] == prev_key] if prev_key else pd.DataFrame()

    def _to_py(v):
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
        return v

    def get_val(df_row, col, default=0):
        if len(df_row) == 0:
            return default
        v = df_row.iloc[0][col]
        return _to_py(v) if pd.notna(v) else default

    metrics_cols = [
        "activity_count", "total_registrations", "total_signins",
        "total_tasks", "total_completed", "avg_signin_rate",
        "avg_completion_rate", "avg_score", "risk_activity_count",
        "total_pending_tasks",
    ]

    comparison = {}
    for col in metrics_cols:
        curr_v = get_val(curr_row, col)
        prev_v = get_val(prev_row, col)
        if prev_v != 0:
            delta_pct = (curr_v - prev_v) / prev_v * 100
        else:
            delta_pct = float("inf") if curr_v > 0 else 0.0
        is_float = isinstance(curr_v, float)
        comparison[col] = {
            "current": round(curr_v, 4) if is_float else curr_v,
            "previous": round(prev_v, 4) if isinstance(prev_v, float) else prev_v,
            "delta": round(float(curr_v) - float(prev_v), 4) if is_float else int(curr_v) - int(prev_v),
            "delta_pct": round(delta_pct, 1) if delta_pct != float("inf") else "N/A",
        }

    comparison["_meta"] = {
        "current_period": current_period,
        "previous_period": prev_key or "无",
        "current_label": get_period_label(current_period, period_type),
        "previous_label": get_period_label(prev_key, period_type) if prev_key else "无",
    }
    return comparison


def get_followup_list(act_metrics: pd.DataFrame, tasks: pd.DataFrame, feedback: pd.DataFrame) -> pd.DataFrame:
    items = []
    for _, act in act_metrics.iterrows():
        if act["task_pending"] > 0:
            pending_tasks = tasks[
                (tasks["activity_id"] == act["activity_id"]) &
                (tasks["status"].isin(["pending", "in_progress"]))
            ]
            for _, t in pending_tasks.iterrows():
                items.append({
                    "activity_id": act["activity_id"],
                    "activity_name": act["name"],
                    "person_in_charge": act["person_in_charge"],
                    "type": "待完成任务",
                    "detail": f"{t['task_name']} - 志愿者: {t['volunteer_id']} ({t['status']})",
                    "priority": "高" if t["status"] == "pending" else "中",
                })
        if act["fb_count"] > 0 and act["avg_score"] < 3.0:
            low_fb = feedback[
                (feedback["activity_id"] == act["activity_id"]) &
                (feedback["score"] <= 2)
            ]
            for _, f in low_fb.iterrows():
                items.append({
                    "activity_id": act["activity_id"],
                    "activity_name": act["name"],
                    "person_in_charge": act["person_in_charge"],
                    "type": "低评分反馈",
                    "detail": f"评分 {f['score']} 分: {f['comment']}",
                    "priority": "高",
                })
        if act["reg_count"] > 0 and act["signin_rate"] < 0.6:
            items.append({
                "activity_id": act["activity_id"],
                "activity_name": act["name"],
                "person_in_charge": act["person_in_charge"],
                "type": "签到率预警",
                "detail": f"签到率 {act['signin_rate']:.0%}，报名 {act['reg_count']} 人，实到 {act['signin_count']} 人",
                "priority": "高",
            })
        if act["date"] < pd.Timestamp(datetime.now()) and act["fb_count"] == 0:
            items.append({
                "activity_id": act["activity_id"],
                "activity_name": act["name"],
                "person_in_charge": act["person_in_charge"],
                "type": "缺少反馈",
                "detail": "活动已结束但未收集到志愿者反馈",
                "priority": "中",
            })
    if not items:
        return pd.DataFrame(columns=["activity_id", "activity_name", "person_in_charge", "type", "detail", "priority"])
    return pd.DataFrame(items).sort_values(["priority", "type"], ascending=[True, True])


def apply_filters(
    act_metrics: pd.DataFrame,
    activities_df: pd.DataFrame,
    registrations: pd.DataFrame,
    signins: pd.DataFrame,
    tasks: pd.DataFrame,
    feedback: pd.DataFrame,
    selected_activities=None,
    selected_persons=None,
    date_range=None,
):
    acts = activities_df.copy()
    if selected_activities:
        acts = acts[acts["activity_id"].isin(selected_activities)]
    if selected_persons:
        acts = acts[acts["person_in_charge"].isin(selected_persons)]
    if date_range and len(date_range) == 2:
        start, end = date_range
        acts = acts[(acts["date"] >= pd.Timestamp(start)) & (acts["date"] <= pd.Timestamp(end))]

    valid_ids = set(acts["activity_id"].unique())
    am = act_metrics[act_metrics["activity_id"].isin(valid_ids)].copy()
    reg = registrations[registrations["activity_id"].isin(valid_ids)].copy()
    sin = signins[signins["activity_id"].isin(valid_ids)].copy()
    tk = tasks[tasks["activity_id"].isin(valid_ids)].copy()
    fb = feedback[feedback["activity_id"].isin(valid_ids)].copy()
    return am, acts, reg, sin, tk, fb

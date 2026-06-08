import pandas as pd
from datetime import datetime, timedelta


REQUIRED_ACTIVITY_COLS = [
    "activity_id", "activity_name", "responsible_person",
    "start_date", "end_date", "location",
]
REQUIRED_CHECKIN_COLS = [
    "checkin_id", "activity_id", "volunteer_name",
    "checkin_time", "status",
]
REQUIRED_TASK_COLS = [
    "task_id", "activity_id", "volunteer_name",
    "task_name", "completion_status",
]
REQUIRED_FEEDBACK_COLS = [
    "feedback_id", "activity_id", "volunteer_name",
    "score", "comment", "feedback_date",
]


def validate_csv(df, required_cols, label):
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label} 缺少必需列: {', '.join(missing)}")
    return True


def parse_activities(df):
    validate_csv(df, REQUIRED_ACTIVITY_COLS, "活动记录")
    df = df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    return df


def parse_checkins(df):
    validate_csv(df, REQUIRED_CHECKIN_COLS, "签到记录")
    df = df.copy()
    df["checkin_time"] = pd.to_datetime(df["checkin_time"], errors="coerce")
    return df


def parse_tasks(df):
    validate_csv(df, REQUIRED_TASK_COLS, "任务记录")
    df = df.copy()
    return df


def parse_feedbacks(df):
    validate_csv(df, REQUIRED_FEEDBACK_COLS, "反馈记录")
    df = df.copy()
    df["feedback_date"] = pd.to_datetime(df["feedback_date"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    return df


def _period_key(dt, mode):
    if pd.isna(dt):
        return None
    if mode == "week":
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    else:
        return f"{dt.year}-{dt.month:02d}"


def _period_label(key, mode):
    if key is None:
        return "未知周期"
    if mode == "week":
        return f"{key} 周"
    return f"{key.replace('-', '年', 1)}月"


def _period_sort_key(key):
    if key is None:
        return ""
    return key


def assign_period(activities, mode):
    df = activities.copy()
    df["period_key"] = df["start_date"].apply(lambda d: _period_key(d, mode))
    df["period_label"] = df["period_key"].apply(lambda k: _period_label(k, mode))
    return df


def _overlap_filter(act, date_range):
    if not date_range or len(date_range) != 2:
        return act
    start, end = date_range
    mask = pd.Series(True, index=act.index)
    if start:
        mask &= act["end_date"] >= pd.Timestamp(start)
    if end:
        mask &= act["start_date"] <= pd.Timestamp(end)
    return act[mask]


def compute_registration_count(activities, checkins):
    if activities.empty or checkins.empty:
        return pd.DataFrame()
    reg = checkins.groupby("activity_id")["volunteer_name"].nunique().reset_index()
    reg.columns = ["activity_id", "报名人数"]
    return reg


def compute_checkin_rate(activities, checkins):
    if activities.empty or checkins.empty:
        return pd.DataFrame()
    total = checkins.groupby("activity_id")["volunteer_name"].nunique().reset_index()
    total.columns = ["activity_id", "报名人数"]
    checked = checkins[checkins["status"] == "已签到"].groupby("activity_id")["volunteer_name"].nunique().reset_index()
    checked.columns = ["activity_id", "签到人数"]
    result = total.merge(checked, on="activity_id", how="left")
    result["签到人数"] = result["签到人数"].fillna(0).astype(int)
    result["签到率"] = (result["签到人数"] / result["报名人数"] * 100).round(1)
    return result


def compute_task_completion_rate(activities, tasks):
    if activities.empty or tasks.empty:
        return pd.DataFrame()
    total = tasks.groupby("activity_id")["task_id"].count().reset_index()
    total.columns = ["activity_id", "任务总数"]
    completed = tasks[tasks["completion_status"] == "已完成"].groupby("activity_id")["task_id"].count().reset_index()
    completed.columns = ["activity_id", "已完成数"]
    result = total.merge(completed, on="activity_id", how="left")
    result["已完成数"] = result["已完成数"].fillna(0).astype(int)
    result["任务完成率"] = (result["已完成数"] / result["任务总数"] * 100).round(1)
    return result


def compute_avg_feedback(feedbacks):
    if feedbacks.empty:
        return pd.DataFrame()
    return feedbacks.groupby("activity_id").agg(
        平均评分=("score", "mean"),
        评分人数=("score", "count"),
    ).reset_index()


def build_period_report(activities, checkins, tasks, feedbacks, mode, date_range=None):
    if activities.empty:
        return pd.DataFrame(), []

    act = assign_period(activities, mode)
    act = _overlap_filter(act, date_range)

    periods = sorted(act["period_key"].dropna().unique(), key=_period_sort_key)

    rows = []
    for pk in periods:
        subset = act[act["period_key"] == pk]
        act_ids = subset["activity_id"].tolist()
        label = _period_label(pk, mode)

        reg_count = 0
        checkin_rate_val = 0.0
        task_rate_val = 0.0
        avg_score_val = 0.0

        if not checkins.empty:
            c_sub = checkins[checkins["activity_id"].isin(act_ids)]
            reg_count = c_sub["volunteer_name"].nunique()
            checked = c_sub[c_sub["status"] == "已签到"]["volunteer_name"].nunique()
            checkin_rate_val = round(checked / reg_count * 100, 1) if reg_count > 0 else 0.0

        if not tasks.empty:
            t_sub = tasks[tasks["activity_id"].isin(act_ids)]
            t_total = len(t_sub)
            t_done = len(t_sub[t_sub["completion_status"] == "已完成"])
            task_rate_val = round(t_done / t_total * 100, 1) if t_total > 0 else 0.0

        if not feedbacks.empty:
            f_sub = feedbacks[feedbacks["activity_id"].isin(act_ids)]
            avg_score_val = round(f_sub["score"].mean(), 2) if not f_sub.empty else 0.0

        rows.append({
            "周期": label,
            "周期键": pk,
            "活动数": len(act_ids),
            "报名人数": reg_count,
            "签到率(%)": checkin_rate_val,
            "任务完成率(%)": task_rate_val,
            "平均反馈评分": avg_score_val,
        })

    report_df = pd.DataFrame(rows)

    trends = []
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        curr = rows[i]
        trends.append({
            "周期": curr["周期"],
            "报名人数变化": curr["报名人数"] - prev["报名人数"],
            "签到率变化(%)": round(curr["签到率(%)"] - prev["签到率(%)"], 1),
            "任务完成率变化(%)": round(curr["任务完成率(%)"] - prev["任务完成率(%)"], 1),
            "评分变化": round(curr["平均反馈评分"] - prev["平均反馈评分"], 2),
        })

    return report_df, trends


def filter_data(activities, checkins, tasks, feedbacks, activity_name=None, responsible=None, date_range=None):
    act = activities.copy()
    if activity_name:
        act = act[act["activity_name"].str.contains(activity_name, na=False)]
    if responsible:
        act = act[act["responsible_person"].str.contains(responsible, na=False)]
    act = _overlap_filter(act, date_range)

    valid_ids = act["activity_id"].tolist()
    c = checkins[checkins["activity_id"].isin(valid_ids)] if not checkins.empty else checkins
    t = tasks[tasks["activity_id"].isin(valid_ids)] if not tasks.empty else tasks
    f = feedbacks[feedbacks["activity_id"].isin(valid_ids)] if not feedbacks.empty else feedbacks
    return act, c, t, f

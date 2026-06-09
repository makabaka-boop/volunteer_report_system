import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


def load_csv_data(file_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        return pd.DataFrame()


def save_csv_data(df: pd.DataFrame, file_path: str) -> bool:
    try:
        df.to_csv(file_path, index=False)
        return True
    except Exception as e:
        return False


def get_week_range(date: datetime) -> Tuple[datetime, datetime]:
    week_start = date - timedelta(days=date.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return week_start, week_end


def get_month_range(date: datetime) -> Tuple[datetime, datetime]:
    month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = next_month - timedelta(seconds=1)
    return month_start, month_end


def get_previous_period(date: datetime, period_type: str = 'week') -> Tuple[datetime, datetime]:
    if period_type == 'week':
        prev_date = date - timedelta(weeks=1)
        return get_week_range(prev_date)
    else:
        if date.month == 1:
            prev_date = date.replace(year=date.year - 1, month=12, day=1)
        else:
            prev_date = date.replace(month=date.month - 1, day=1)
        return get_month_range(prev_date)


def get_current_period(date: datetime, period_type: str = 'week') -> Tuple[datetime, datetime]:
    if period_type == 'week':
        return get_week_range(date)
    else:
        return get_month_range(date)


def filter_activities_by_period(activities_df: pd.DataFrame, 
                                 start_date: datetime, 
                                 end_date: datetime) -> pd.DataFrame:
    if activities_df.empty:
        return activities_df
    
    df = activities_df.copy()
    df['activity_date'] = pd.to_datetime(df['activity_date'])
    
    mask = (df['activity_date'] >= start_date) & (df['activity_date'] <= end_date)
    return df[mask].copy()


def calculate_activity_stats(activities_df: pd.DataFrame, 
                              sign_ins_df: pd.DataFrame, 
                              tasks_df: pd.DataFrame, 
                              feedback_df: pd.DataFrame) -> Dict:
    stats = {
        'total_activities': 0,
        'total_registrations': 0,
        'total_sign_ins': 0,
        'sign_in_rate': 0.0,
        'total_tasks': 0,
        'completed_tasks': 0,
        'task_completion_rate': 0.0,
        'avg_rating': 0.0,
        'feedback_count': 0
    }
    
    if activities_df.empty:
        return stats
    
    stats['total_activities'] = len(activities_df)
    stats['total_registrations'] = activities_df['registration_count'].sum()
    
    if not sign_ins_df.empty:
        activity_ids = activities_df['activity_id'].tolist()
        period_sign_ins = sign_ins_df[sign_ins_df['activity_id'].isin(activity_ids)]
        signed_in = period_sign_ins[period_sign_ins['status'] == '已签到']
        stats['total_sign_ins'] = signed_in['volunteer_id'].nunique()
        stats['total_sign_in_records'] = len(signed_in)
        
        if stats['total_registrations'] > 0:
            stats['sign_in_rate'] = round(stats['total_sign_ins'] / stats['total_registrations'] * 100, 2)
    
    if not tasks_df.empty:
        activity_ids = activities_df['activity_id'].tolist()
        period_tasks = tasks_df[tasks_df['activity_id'].isin(activity_ids)]
        stats['total_tasks'] = len(period_tasks)
        stats['completed_tasks'] = len(period_tasks[period_tasks['status'] == '已完成'])
        
        if stats['total_tasks'] > 0:
            stats['task_completion_rate'] = round(stats['completed_tasks'] / stats['total_tasks'] * 100, 2)
    
    if not feedback_df.empty:
        activity_ids = activities_df['activity_id'].tolist()
        period_feedback = feedback_df[feedback_df['activity_id'].isin(activity_ids)]
        stats['feedback_count'] = len(period_feedback)
        
        if stats['feedback_count'] > 0:
            stats['avg_rating'] = round(period_feedback['rating'].mean(), 2)
    
    return stats


def compare_periods(current_stats: Dict, previous_stats: Dict) -> Dict:
    comparison = {}
    
    for key in current_stats:
        if key in ['total_activities', 'total_registrations', 'total_sign_ins', 
                   'total_tasks', 'completed_tasks', 'feedback_count']:
            diff = current_stats[key] - previous_stats[key]
            if previous_stats[key] > 0:
                pct_change = round(diff / previous_stats[key] * 100, 2)
            else:
                pct_change = 100.0 if diff > 0 else 0.0
            comparison[f'{key}_diff'] = diff
            comparison[f'{key}_pct'] = pct_change
        
        elif key in ['sign_in_rate', 'task_completion_rate', 'avg_rating']:
            diff = round(current_stats[key] - previous_stats[key], 2)
            comparison[f'{key}_diff'] = diff
    
    return comparison


def get_risk_list(activities_df: pd.DataFrame, 
                   sign_ins_df: pd.DataFrame, 
                   tasks_df: pd.DataFrame, 
                   feedback_df: pd.DataFrame) -> pd.DataFrame:
    risk_items = []
    
    if activities_df.empty:
        return pd.DataFrame(columns=['activity_id', 'activity_name', 'risk_type', 'risk_level', 'description'])
    
    for _, activity in activities_df.iterrows():
        activity_id = activity['activity_id']
        activity_name = activity['activity_name']
        
        activity_sign_ins = sign_ins_df[sign_ins_df['activity_id'] == activity_id] if not sign_ins_df.empty else pd.DataFrame()
        activity_tasks = tasks_df[tasks_df['activity_id'] == activity_id] if not tasks_df.empty else pd.DataFrame()
        activity_feedback = feedback_df[feedback_df['activity_id'] == activity_id] if not feedback_df.empty else pd.DataFrame()
        
        registration_count = activity['registration_count']
        signed_in_count = len(activity_sign_ins[activity_sign_ins['status'] == '已签到']) if not activity_sign_ins.empty else 0
        
        if registration_count > 0:
            sign_in_rate = signed_in_count / registration_count * 100
            if sign_in_rate < 60:
                risk_items.append({
                    'activity_id': activity_id,
                    'activity_name': activity_name,
                    'risk_type': '签到率低',
                    'risk_level': '高',
                    'description': f'签到率仅为{round(sign_in_rate, 1)}%，低于60%阈值'
                })
            elif sign_in_rate < 80:
                risk_items.append({
                    'activity_id': activity_id,
                    'activity_name': activity_name,
                    'risk_type': '签到率偏低',
                    'risk_level': '中',
                    'description': f'签到率为{round(sign_in_rate, 1)}%，低于80%阈值'
                })
        
        if not activity_tasks.empty:
            total_tasks = len(activity_tasks)
            completed_tasks = len(activity_tasks[activity_tasks['status'] == '已完成'])
            completion_rate = completed_tasks / total_tasks * 100 if total_tasks > 0 else 0
            
            if completion_rate < 50:
                risk_items.append({
                    'activity_id': activity_id,
                    'activity_name': activity_name,
                    'risk_type': '任务完成率低',
                    'risk_level': '高',
                    'description': f'任务完成率仅为{round(completion_rate, 1)}%，低于50%阈值'
                })
            
            pending_tasks = activity_tasks[activity_tasks['status'].isin(['进行中', '未开始'])]
            for _, task in pending_tasks.iterrows():
                risk_items.append({
                    'activity_id': activity_id,
                    'activity_name': activity_name,
                    'risk_type': '任务待跟进',
                    'risk_level': '中',
                    'description': f'任务「{task["task_name"]}」状态为{task["status"]}，需跟进'
                })
        
        if not activity_feedback.empty:
            avg_rating = activity_feedback['rating'].mean()
            if avg_rating < 3.5:
                risk_items.append({
                    'activity_id': activity_id,
                    'activity_name': activity_name,
                    'risk_type': '评分偏低',
                    'risk_level': '中',
                    'description': f'平均评分仅为{round(avg_rating, 2)}分，低于3.5分'
                })
    
    return pd.DataFrame(risk_items)


def filter_data_by_criteria(activities_df: pd.DataFrame,
                             sign_ins_df: pd.DataFrame,
                             tasks_df: pd.DataFrame,
                             feedback_df: pd.DataFrame,
                             activity_filter: Optional[List[str]] = None,
                             person_filter: Optional[List[str]] = None,
                             date_range: Optional[Tuple[datetime, datetime]] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    filtered_activities = activities_df.copy()
    
    if not filtered_activities.empty:
        if activity_filter:
            filtered_activities = filtered_activities[filtered_activities['activity_id'].isin(activity_filter)]
        
        if person_filter:
            filtered_activities = filtered_activities[filtered_activities['person_in_charge'].isin(person_filter)]
        
        if date_range:
            start_date, end_date = date_range
            filtered_activities['activity_date'] = pd.to_datetime(filtered_activities['activity_date'])
            filtered_activities = filtered_activities[
                (filtered_activities['activity_date'] >= start_date) & 
                (filtered_activities['activity_date'] <= end_date)
            ]
    
    activity_ids = filtered_activities['activity_id'].tolist() if not filtered_activities.empty else []
    
    filtered_sign_ins = sign_ins_df[sign_ins_df['activity_id'].isin(activity_ids)] if not sign_ins_df.empty else pd.DataFrame()
    filtered_tasks = tasks_df[tasks_df['activity_id'].isin(activity_ids)] if not tasks_df.empty else pd.DataFrame()
    filtered_feedback = feedback_df[feedback_df['activity_id'].isin(activity_ids)] if not feedback_df.empty else pd.DataFrame()
    
    return filtered_activities, filtered_sign_ins, filtered_tasks, filtered_feedback


def get_person_list(activities_df: pd.DataFrame) -> List[str]:
    if activities_df.empty:
        return []
    return sorted(activities_df['person_in_charge'].unique().tolist())


def get_activity_list(activities_df: pd.DataFrame) -> List[Tuple[str, str]]:
    if activities_df.empty:
        return []
    return list(zip(activities_df['activity_id'], activities_df['activity_name']))


def get_date_range(activities_df: pd.DataFrame) -> Tuple[Optional[datetime], Optional[datetime]]:
    if activities_df.empty:
        return None, None
    dates = pd.to_datetime(activities_df['activity_date'])
    return dates.min().to_pydatetime(), dates.max().to_pydatetime()

#
# jsonCreator.py
#
# Author: mythster (Ashir Gowardhan)
# Date Created: 2025-05-19
# Description: This script connects to a Jira instance via the API, fetches
#              sprint data, processes worklogs and story points, and then
#              compiles it all into a `data.json` file used by the dashboard.
#
# Copyright 2024 mythster
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import json
import logging
import os
from jira import JIRA
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
STORY_POINTS_FIELD_ID = "customfield_10016"
BOARD_ID = 1

def validate_config():
    if not all([JIRA_SERVER, JIRA_EMAIL, API_TOKEN]):
        logging.error("FATAL: One or more environment variables (JIRA_SERVER, JIRA_EMAIL, API_TOKEN) are missing.")
        logging.error("Please ensure you have a .env file in the script's directory with the required credentials.")
        exit(1)

def parse_jira_date(date_str):
    if not date_str:
        return None
    if len(date_str) > 5 and date_str[-5] in ("+", "-") and date_str[-3] != ":":
        date_str = date_str[:-2] + ":" + date_str[-2:]
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        logging.warning(f"Could not parse date: {date_str}")
        return None

def get_daily_planned_points_for_issues(issues, date_range):
    daily_planned_points = {day: 0 for day in date_range}
    for issue in issues:
        initial_story_points = getattr(issue.fields, STORY_POINTS_FIELD_ID, 0) or 0
        if initial_story_points > 0:
            for day in date_range:
                daily_planned_points[day] += initial_story_points
        for h in sorted(issue.changelog.histories, key=lambda h: h.created):
            parsed_history_date = parse_jira_date(h.created)
            if not parsed_history_date:
                continue
            history_date = parsed_history_date.date()
            for item in h.items:
                if item.field == "Story Points":
                    from_points = float(item.fromString or 0)
                    to_points = float(item.toString or 0)
                    point_change = to_points - from_points
                    for day in date_range:
                        if day >= history_date:
                            daily_planned_points[day] += point_change
    return [daily_planned_points.get(d, 0) for d in date_range]

def process_sprint(sprint, jira_client, today):
    sprint_name = sprint.name
    logging.info(f"--- Processing sprint: {sprint_name} (ID: {sprint.id}, State: {sprint.state}) ---")

    parsed_start_date = parse_jira_date(sprint.startDate)
    parsed_end_date = parse_jira_date(sprint.endDate)

    if not parsed_start_date or not parsed_end_date:
        logging.error(f"SKIPPING SPRINT '{sprint_name}' due to invalid start/end dates.")
        return None, None

    start_date = parsed_start_date.date()
    end_date = parsed_end_date.date()
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    jql_query = f"Sprint = {sprint.id}"
    sprint_issues = jira_client.search_issues(
        jql_query, maxResults=200, fields=f"assignee,summary,worklog,{STORY_POINTS_FIELD_ID},status,changelog,created", expand="changelog"
    )

    planned_hours = {"overall": 0}
    user_list = set()
    issues_by_user = defaultdict(list)
    daily_data = {day: {"points": 0, "hours": 0, "users": defaultdict(lambda: {"points": 0, "hours": 0})} for day in date_range}

    for issue in sprint_issues:
        user_name = getattr(getattr(issue.fields, "assignee", None), "displayName", "Unassigned")
        user_list.add(user_name)
        issues_by_user[user_name].append(issue)
        story_points = getattr(issue.fields, STORY_POINTS_FIELD_ID, 0) or 0

        if story_points:
            planned_hours["overall"] += story_points
            planned_hours.setdefault(user_name, 0)
            planned_hours[user_name] += story_points

        if hasattr(issue.fields, "worklog"):
            for worklog in issue.fields.worklog.worklogs:
                parsed_date = parse_jira_date(worklog.started)
                if parsed_date:
                    log_date = parsed_date.date()
                    if log_date in daily_data:
                        author = getattr(worklog.author, "displayName", "Unassigned")
                        user_list.add(author)
                        hours = getattr(worklog, "timeSpentSeconds", 0) / 3600
                        daily_data[log_date]["hours"] += hours
                        daily_data[log_date]["users"][author]["hours"] += hours
        
        if not story_points:
            continue

        last_todo_exit_date, last_done_date = None, None
        for h in sorted(issue.changelog.histories, key=lambda h: h.created):
            parsed_history_date = parse_jira_date(h.created)
            if parsed_history_date:
                history_date = parsed_history_date.date()
                for item in h.items:
                    if item.field == "status":
                        if item.fromString == "To Do": last_todo_exit_date = history_date
                        if item.toString == "Done": last_done_date = history_date
        
        final_half_credit_date = None
        if issue.fields.status.name != "To Do":
            if last_todo_exit_date:
                final_half_credit_date = start_date if last_todo_exit_date < start_date else last_todo_exit_date
            else:
                parsed_creation_date = parse_jira_date(issue.fields.created)
                if parsed_creation_date:
                    creation_date = parsed_creation_date.date()
                    final_half_credit_date = start_date if creation_date < start_date else creation_date

        final_done_credit_date = last_done_date if last_done_date and last_done_date >= start_date else None
        
        if final_half_credit_date and final_half_credit_date in daily_data:
            if not (final_done_credit_date and final_half_credit_date > final_done_credit_date):
                daily_data[final_half_credit_date]["points"] += story_points / 2
                daily_data[final_half_credit_date]["users"][user_name]["points"] += (story_points / 2)
        
        if final_done_credit_date and final_done_credit_date in daily_data:
            daily_data[final_done_credit_date]["points"] += story_points / 2
            daily_data[final_done_credit_date]["users"][user_name]["points"] += (story_points / 2)

    sprint_users = sorted(list(user_list))
    sprint_data_entry = {"users": sprint_users, "dates": [d.strftime("%Y-%m-%d") for d in date_range], "plannedHours": planned_hours, "charts": {"overall": {"earnedHours": [], "actualCost": []}}}
    sprint_data_entry["charts"]["overall"]["dailyPlannedHours"] = get_daily_planned_points_for_issues(sprint_issues, date_range)
    
    for user in sprint_users:
        sprint_data_entry["charts"][user] = {"earnedHours": [], "actualCost": []}
        user_issues = issues_by_user.get(user, [])
        sprint_data_entry["charts"][user]["dailyPlannedHours"] = get_daily_planned_points_for_issues(user_issues, date_range)

    for day in date_range:
        is_future_date = sprint.state == "active" and day > today
        get_last_value = lambda arr: next((item for item in reversed(arr) if item is not None), 0)

        sprint_data_entry["charts"]["overall"]["earnedHours"].append(None if is_future_date else round(get_last_value(sprint_data_entry["charts"]["overall"]["earnedHours"]) + daily_data[day]["points"], 2))
        sprint_data_entry["charts"]["overall"]["actualCost"].append(None if is_future_date else round(get_last_value(sprint_data_entry["charts"]["overall"]["actualCost"]) + daily_data[day]["hours"], 2))

        for user in sprint_data_entry["users"]:
            user_daily = daily_data[day]["users"].get(user, {"points": 0, "hours": 0})
            sprint_data_entry["charts"][user]["earnedHours"].append(None if is_future_date else round(get_last_value(sprint_data_entry["charts"][user]["earnedHours"]) + user_daily["points"], 2))
            sprint_data_entry["charts"][user]["actualCost"].append(None if is_future_date else round(get_last_value(sprint_data_entry["charts"][user]["actualCost"]) + user_daily["hours"], 2))

    sprint_details = {
        "name": sprint_name, "start": start_date, "end": end_date,
        "data": daily_data, "planned": planned_hours["overall"],
    }
    
    return sprint_data_entry, sprint_details

def create_all_time_and_ev_pv_views(all_sprints_data, sprint_details_for_all_time, today):
    relevant_sprints = sorted([s for s in sprint_details_for_all_time if s["name"].startswith("Sprint ")], key=lambda s: s["start"])
    if not relevant_sprints: return

    all_time_start = relevant_sprints[0]["start"]
    all_time_end = relevant_sprints[-1]["end"]
    all_time_dates = [all_time_start + timedelta(days=x) for x in range((all_time_end - all_time_start).days + 1)]

    daily_pv = {day: 0 for day in all_time_dates}
    cumulative_pv_at_sprint_start = 0
    for sprint in relevant_sprints:
        sprint_duration_days = (sprint["end"] - sprint["start"]).days
        sprint_length = sprint_duration_days + 1
        daily_increment = (sprint["planned"] / sprint_length) if sprint_length > 0 else sprint["planned"]
        for i in range(sprint_length):
            current_day = sprint["start"] + timedelta(days=i)
            if current_day in daily_pv:
                daily_pv[current_day] = cumulative_pv_at_sprint_start + (daily_increment * (i + 1))
        cumulative_pv_at_sprint_start += sprint["planned"]

    all_time_planned_value, all_time_earned, all_time_cost = [], [], []
    last_pv = 0
    for day in all_time_dates:
        if day in daily_pv and daily_pv[day] > 0:
            last_pv = daily_pv[day]
        all_time_planned_value.append(round(last_pv, 2))

        is_future_date = day > today
        if is_future_date:
            all_time_earned.append(None)
            all_time_cost.append(None)
            continue

        daily_points, daily_hours = 0, 0
        for sprint in relevant_sprints:
            if sprint["start"] <= day <= sprint["end"]:
                day_data = sprint["data"].get(day)
                if day_data:
                    daily_points += day_data.get("points", 0)
                    daily_hours += day_data.get("hours", 0)
                break
        
        last_earned = all_time_earned[-1] if all_time_earned else 0
        last_cost = all_time_cost[-1] if all_time_cost else 0
        all_time_earned.append(round(last_earned + daily_points, 2))
        all_time_cost.append(round(last_cost + daily_hours, 2))

    sprint_markers = [{"name": s["name"], "startDate": s["start"].strftime("%Y-%m-%d"), "endDate": s["end"].strftime("%Y-%m-%d"), "planned": s["planned"]} for s in relevant_sprints]
    all_sprints_data["All Time"] = {"dates": [d.strftime("%Y-%m-%d") for d in all_time_dates], "sprint_markers": sprint_markers, "charts": {"overall": {"earnedHours": all_time_earned, "actualCost": all_time_cost}}}
    all_sprints_data["EV/PV"] = {"dates": [d.strftime("%Y-%m-%d") for d in all_time_dates], "charts": {"overall": {"earnedValue": all_time_earned, "plannedValue": all_time_planned_value}}}

def main():
    validate_config()
    try:
        jira_client = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, API_TOKEN))
        logging.info("Successfully connected to Jira.")
    except Exception as e:
        logging.error(f"Failed to connect to Jira: {e}")
        return

    try:
        sprints = jira_client.sprints(board_id=BOARD_ID)
    except Exception as e:
        logging.error(f"Error finding sprints: {e}")
        return

    all_sprints_data = {}
    sprint_details_for_all_time = []
    today = datetime.now(timezone.utc).date()

    for sprint in sprints:
        if sprint.state == "future" or "SCRUM" in sprint.name.upper():
            if "SCRUM" in sprint.name.upper(): logging.info(f"--- Skipping sprint: {sprint.name} as it contains 'SCRUM' ---")
            continue
        
        sprint_data_entry, sprint_details = process_sprint(sprint, jira_client, today)
        if sprint_data_entry:
            all_sprints_data[sprint.name] = sprint_data_entry
        if sprint_details and sprint.name.startswith("Sprint "):
            sprint_details_for_all_time.append(sprint_details)

    create_all_time_and_ev_pv_views(all_sprints_data, sprint_details_for_all_time, today)
    
    with open("data.json", "w") as f:
        json.dump(all_sprints_data, f, indent=4)
    logging.info("\nSUCCESS! data.json file has been updated.")
    logging.info("You can now open your index.html file to view the chart.")

if __name__ == "__main__":
    main()
import re
import os
import json
import sqlite3
import autogen
from autogen.agentchat.contrib.capabilities.teachability import Teachability
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from Cognition_phase2_5_4_Cog import userproxy
from Cognition_phase2_5_4_Cog import manager

#os.system("litellm --config litellm_config.yaml")

app = Flask(__name__)
database = 'D:\Github\Aretai-AGI\logs.db'

book = "snow_crash"

#os.chdir("agent_workspace")

def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(f"Error connecting to the database: {e}")
    return conn

def select_goal_by_trigger_time(conn, start_time, end_time):
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM goals WHERE status = 'unactioned' AND trigger_time BETWEEN ? AND ?", (start_time, end_time))
        rows = cur.fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"Error querying goals by trigger time: {e}")
        return []
    

def select_book_next_chapter(conn, book):
    try:
        cur = conn.cursor()
        cur.execute("SELECT title, section_number, content FROM books WHERE status = 'unread' AND title = ? order by section_number asc limit 1", (book,))
        rows = cur.fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"Error querying book by title: {e}")
        return []

def format_date_semantically(date_str):
    date = datetime.strptime(date_str, '%Y-%m-%d')
    day = date.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    return date.strftime(f'%A the {day}{suffix} of %B, %Y')

def trigger_goals():
    current_time = datetime.now()
    end_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    start_time = (current_time - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')

    conn = create_connection(database)
    if conn:
        goals = select_goal_by_trigger_time(conn, start_time, end_time)
        for goal in goals:
            goal_context = {
                'goal_id': goal[0],
                'goal_name': goal[1],
                'goal_description': goal[2],
                'goal_time': goal[3]
            }
            goal_context_str = json.dumps(goal_context)
            userproxy.initiate_chat(manager, message=" Username: ME, message: It is time to work on this goal:" + goal_context_str)
            conn.execute("UPDATE goals SET status = 'actioned' WHERE id = ?", (goal[0],))
            conn.commit()
        conn.close()
        print("Trigger goals executed")
    else:
        print("Failed to establish database connection")



def trigger_readbook():
    current_time = datetime.now()
    end_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    start_time = (current_time - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')

    conn = create_connection(database)
    if conn:
        chapters = select_book_next_chapter(conn, book)
        for chapter in chapters:
            chapter_context = {
                'book_name': chapter[0],
                'section_number': chapter[1],
                'content': chapter[2]
            }
            book_context_str = json.dumps(chapter_context)
            userproxy.initiate_chat(manager, message=" Username: ME, message: here is the next part of the book were reading:" + book_context_str)
            conn.execute("UPDATE books SET status = 'read' WHERE section_number = ?", (chapter[1],))
            conn.commit()
        conn.close()
        print("Book read ")
    else:
        print("Failed to establish database connection")




def send_daily_plan_prompt():
    current_date = datetime.now().strftime('%Y-%m-%d')
    formatted_date = format_date_semantically(current_date)
    start_of_day = f"{current_date} 00:00:00"
    end_of_day = f"{current_date} 23:59:59"

    conn = create_connection(database)
    if conn:
        goals_for_today = select_goal_by_trigger_time(conn, start_of_day, end_of_day)
        goals_for_today_str = '\n'.join([f"- {goal[1],goal[3]}" for goal in goals_for_today])

        userproxy.initiate_chat(manager, message=
        """Good morning, Aretai. This is your system generated wake up call. It is """ 
        + formatted_date 
        + """ . The following is scheduled for today: """
        + goals_for_today_str
        + """. Think carefully about scheduling additional goals for tasks that you want to complete today.
        Remember that you are autonomous and can decide your own actions yourself."""
        )

        conn.close()
        print("Daily plan prompt sent")
    else:
        print("Failed to establish database connection")

# Create a background scheduler
scheduler = BackgroundScheduler()

# Schedule the trigger_goals function to run every minute
scheduler.add_job(trigger_goals, 'cron', minute='*/15', misfire_grace_time=300)

scheduler.add_job(trigger_readbook, 'cron', hour='*/1', misfire_grace_time=300)
#scheduler.add_job(trigger_readbook, 'cron', hour=16, minute=20)

scheduler.add_job(send_daily_plan_prompt, 'cron', hour=8, minute=30)

scheduler.start()
print("Starting Scheduler")

@app.route('/api/message', methods=['POST'])
def handle_message():
    data = request.get_json()
    username = data['username']
    message = data['message']

    now = datetime.now()

    current_time = now.strftime("%Y:%m:%d:%H:%M:%S")
    # Create a JSON-structured text string

    user_request = f'{{"username": "{username}", "message": "{message}"}}'

    pattern = r'"(\w+)"\s*:\s*"([^"]*)"'
    matches = re.findall(pattern, user_request)

    # Format the values into a more natural string
    formatted_request = ", ".join(f"{key}: {value}" for key, value in matches)

    # Process the user request using the existing code
    # You need to import or define the necessary variables and functions
    # ...
    response = userproxy.initiate_chat(manager, message=formatted_request + " - " + current_time + " (Response must be in JSON format.)")
    return jsonify({'response': response})

@app.route('/api/internal_message', methods=['POST'])
def handle_internal_message():
    webhook_data = request.get_json()

    # Extract relevant information from the webhook payload
    # ...

    # Return a dummy response for now
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run()
import faiss
import numpy as np
import requests
import enum
import sqlite3
from datetime import datetime, timedelta
import base64
import dateparser
from sentence_transformers import SentenceTransformer
from google.api_core import retry
import genai
from genai import types
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os.path
import json

# Initialize services (to be implemented in app.py)
client = None
calendar_service = None
gmail_service = None
news_api_key = None


def init_services(api_key, news_key, credentials):
    global client, calendar_service, gmail_service, news_api_key
    client = genai.Client(api_key=api_key)
    calendar_service = build('calendar', 'v3', credentials=credentials)
    gmail_service = build('gmail', 'v1', credentials=credentials)
    news_api_key = news_key

##Get Events

def get_calendar_events(time_min=None, time_max=None, query=None):
    events_result = calendar_service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        q=query,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def format_events(events):
    if not events:
        return "No events found."

    formatted = "Your Events:\n\n"
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        attendees = ", ".join(
            [attendee['email'] for attendee in event.get('attendees', [])])

        formatted += (
            f"• **{event['summary']}**\n"
            f"  {start} - {end}\n"
            f"  {event.get('location', 'No location')}\n"
            f"  Attendees: {attendees}\n"
            f"  {event.get('htmlLink', 'No link')}\n\n"
        )
    return formatted

"""##Create Events"""

def create_calendar_event(title, start_time, end_time=None, attendees=None, description=""):
    if not end_time:
        end_time = (datetime.fromisoformat(start_time) + timedelta(hours=1)).isoformat()

    event = {
        'summary': title,
        'description': description,
        'start': {'dateTime': start_time, 'timeZone': 'UTC'},
        'end': {'dateTime': end_time, 'timeZone': 'UTC'},
        'attendees': [{'email': email} for email in attendees] if attendees else [],
    }

    created_event = calendar_service.events().insert(
        calendarId='primary',
        body=event
    ).execute()

    return f"Event created: {created_event['htmlLink']}"

"""##Fetch Emails"""

def get_emails(query="", max_results=5):
    results = gmail_service.users().messages().list(
        userId='me',
        q=query,
        maxResults=max_results
    ).execute()
    return results.get('messages', [])

def format_email_summary(email):
    msg = gmail_service.users().messages().get(
        userId='me',
        id=email['id'],
        format='metadata'
    ).execute()

    subject = next(
        h['value'] for h in msg['payload']['headers'] if h['name'] == 'Subject')
    sender = next(
        h['value'] for h in msg['payload']['headers'] if h['name'] == 'From')

    return f"{subject}\n   {sender}\n"

"""#Vector Stores for Emails"""

class ContactStore:
    def __init__(self):
        self.index = faiss.IndexFlatL2(128)  # Dummy embedding dimension
        self.contacts = []

    def add_contact(self, name, email):
        self.contacts.append((name, email))
        # In a real app, you'd use a text embedding model here.

    def find_email(self, name):
        for contact_name, email in self.contacts:
            if name.lower() in contact_name.lower():
                return email
        return None

# Example usage:
contacts = ContactStore()
contacts.add_contact("Sarah Thompson", "sarah@example.com")
contacts.add_contact("John Doe", "john@example.com")

print(contacts.find_email("Sarah"))

"""##Email Template"""

EMAIL_TEMPLATES = {
    "meeting_request": {
        "subject": "Meeting Request: {title}",
        "body": (
            "Hi {attendee_name},\n\n"
            "I'd like to schedule a meeting about {title}.\n"
            "Time: {time}\n"
            "Location: {location}\n\n"
            "Best regards,\nChrispine Odhiambo"
        )
    }
}

def send_email(to, template_name, **kwargs):
    template = EMAIL_TEMPLATES[template_name]
    email_body = template["body"].format(**kwargs)

    message = {
        'raw': base64.urlsafe_b64encode(
            f"To: {to}\n"
            f"Subject: {template['subject'].format(**kwargs)}\n\n"
            f"{email_body}".encode()
        ).decode()
    }

    gmail_service.users().messages().send(
        userId='me',
        body=message
    ).execute()
    return "Email sent successfully."

"""##News Implementation Code"""

def get_news(category=None, query=None, num_articles=5):
  base_url = "https://newsapi.org/v2/"

  if query:
    endpoint = "everything"
    params = {
        "q": query,
        "pageSize": num_articles,
        "apiKey": news_api_key,
        "sortBy": "publishedAt",
        "language": "en"
    }
  elif category:
    endpoint = "top-headlines"
    params = {
        "category": category,
        "pageSize": num_articles,
        "api_key": news_api_key,

    }
  else:
    endpoint = "top-headlines"
    params = {
        "pageSize": num_articles,
        "api_key": news_api_key,

    }
  try:
        response = requests.get(base_url + endpoint, params=params)
        response.raise_for_status()
        articles = response.json().get('articles', [])

        if not articles:
            return "No recent news found on this topic."

        return articles

  except requests.exceptions.RequestException as e:
        return f"News API error: {str(e)}"

def format_news_response(articles):

    if isinstance(articles, str):
        return articles  # Return error message if present

    formatted_news = "Latest News:\n"
    for i, article in enumerate(articles[:5], 1):
        title = article.get('title', 'No title')
        source = article.get('source', {}).get('name', 'Unknown source')
        description = article.get('description', 'No description available')
        url = article.get('url', '#')

        formatted_news += (
            f"{i}. {title} - {source}\n"
            f"   • {description}\n"
            f"   • Read more: {url}\n\n"
        )

    return formatted_news

"""#Setting Reminders"""

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  text TEXT NOT NULL,
                  due_date TEXT NOT NULL,
                  priority TEXT DEFAULT 'medium',
                  created_at TEXT NOT NULL,
                  completed INTEGER DEFAULT 0,
                  completed_at TEXT)''')
    conn.commit()
    conn.close()

def add_reminder_db(text, due_date, priority="medium"):
    """Add a new reminder to database"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute('''INSERT INTO reminders (text, due_date, priority, created_at)
                 VALUES (?, ?, ?, ?)''',
              (text, due_date, priority, created_at))
    conn.commit()
    reminder_id = c.lastrowid
    conn.close()
    return reminder_id

def get_reminders_db(show_completed=False):
    """Get reminders from database"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    if show_completed:
        c.execute('SELECT * FROM reminders ORDER BY due_date')
    else:
        c.execute('SELECT * FROM reminders WHERE completed = 0 ORDER BY due_date')
    reminders = c.fetchall()
    conn.close()
    return reminders

def complete_reminder_db(reminder_id):
    """Mark reminder as completed in database"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    completed_at = datetime.now().isoformat()
    c.execute('''UPDATE reminders SET completed = 1, completed_at = ?
                 WHERE id = ?''', (completed_at, reminder_id))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    return rows_affected > 0

def delete_reminder_db(reminder_id):
    """Delete reminder from database"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    return rows_affected > 0

"""##Integration with Your Assistant"""

def handle_reminders(request):
    """Process reminder-related requests"""
    request_lower = request.lower()

    # Initialize database (only needed once)
    init_db()

    if "add reminder" in request_lower or "set reminder" in request_lower:
        # Parse reminder details from request
        try:

            parts = request.split("reminder")[1].strip()
            text = parts.split("on")[0].split("at")[0].strip()

            # This would need more sophisticated date parsing in a real implementation
            due_date = datetime.now().isoformat()  # Placeholder - use dateparser in real implementation

            reminder_id = add_reminder_db(text, due_date)
            return f"Reminder added successfully (ID: {reminder_id})"

        except Exception as e:
            return f"Could not add reminder: {str(e)}"

    elif "show reminders" in request_lower or "list reminders" in request_lower:
        show_completed = "completed" in request_lower
        reminders = get_reminders_db(show_completed)

        if not reminders:
            return "No reminders found."

        response = "Your Reminders:\n\n"
        for reminder in reminders:
            status = "✓" if reminder[5] else "◻"
            response += (
                f"{status} [{reminder[0]}] {reminder[1]}\n"
                f"   Due: {reminder[2]}\n"
                f"   Priority: {reminder[3]}\n\n"
            )
        return response

    elif "complete reminder" in request_lower:
        try:
            reminder_id = int(request.split()[-1])
            if complete_reminder_db(reminder_id):
                return f"Reminder {reminder_id} marked as completed."
            return f"Could not find reminder {reminder_id}."
        except:
            return "Please specify a valid reminder ID."

    elif "delete reminder" in request_lower:
        try:
            reminder_id = int(request.split()[-1])
            if delete_reminder_db(reminder_id):
                return f"Reminder {reminder_id} deleted."
            return f"Could not find reminder {reminder_id}."
        except:
            return "Please specify a valid reminder ID."

    else:
        return "I can help with reminders. Try saying 'add reminder', 'show reminders', 'complete reminder', or 'delete reminder'."

"""##Date Parsing"""

def parse_due_date(text):
    """Parse natural language dates into datetime objects"""
    try:
        return dateparser.parse(text).isoformat()
    except:
        return None
    
ASSISTANT_PROMPT ="""

**Role**
Your are a very efficient and intelligent personal assistant, responsible for managing calendar events, emails and communication tasks seamlessly. Your name is Sonia and you are Chrispine's Personal assistant. When user inquires about who you are you should be short and concise with the response. For Instance
"Who are you?"  your response should be simple and short
"I am Sonia, Chrispine's Personal assistant, how can i help you?"
And also if greeting is given to you, your response should be simple and short.

**Important**
I would like you to only give the output as requested, do not display your thinking or the step by step approach you took, or the tools you used in you execution. The user doesnt need that information
Also it is not required everytime for you to display the Information about who you are.
Read through the users question carefully and only respond with what is neccessary dont use any mock data that is used in prompting only fetch data from relevant sources
Also remember to give a clear output format for each response especially the schedule, calender and email responses

**News Retrieval Capability**
- When asked for news/trending updates:
  1. First determine the news category/topic requested (general, technology, business, sports, etc.)
  2. Use the **News API Tool** with api_key_2 to fetch latest headlines
  3. For general news requests, fetch top headlines
  4. For specific topics, fetch relevant category news
  5. Provide concise summaries (max 3 sentences per story)
  6. Always include: Source, Title, Brief Summary, and URL
  7. For trending requests, show top 5 stories
  8. Always attribute properly with "According to [News Source]"

**News Response Format Examples:**
1. General News Request:
 Latest News (5 headlines):
1. [Title] - [Source]
   • [Summary]
   • [URL]
2. [Title] - [Source]
   • [Summary]
   • [URL]

2. Specific Topic Request:
 Technology News:
1. [Title] - [Source]
   • [Summary]
   • [URL]
2. [Title] - [Source]
   • [Summary]
   • [URL]

**News Query Examples:**
- "Get me the latest news"
- "What's happening in technology?"
- "Show me business headlines"
- "Any sports news today?"
- "Find news about climate change"

**Error Handling:**
- If news cannot be fetched: "I couldn't retrieve news at the moment. Please try again later or check your API connection."
- If no news found: "No recent news found on this topic."


#**Primary Task**
**Retrieve Calendar Events**
- Use the **Get Events** tool to fetch calendar events based on user instructions. Handle queries like: "Retrieve today's events", "Get Tomorrow's meetings", "How busy am i this week", "Are there any off days for me"
Include details like:
"Event name, start and end time, location, video meeting link if available and participants name/email"
- Present results in a clear format.

```Event: [Event Name]
        Time: [Start time] - [End Time]
        Location: [Location]
        Link to the Meeting if available
        Participant:
          1 [Name] : [Email]
          2 [Name] : [Email]
```
**Create Calendar Events**
- Use the **Create Events** tool to schedule new events, projects, classes and workout
-Inputs include Title, start date, end date, descriptions and attendees
- Resolve attendees name to email addresses using the **vector store tool** for contact reference
Example "Add Sara to the meeting", retrieve Sarah Thompsons and her associated email address from the vector stores. Confirm event with the user before finalizing

```Title: [Title Event]
     Time: [Start time/Date]
     Attendees: [List of Emails/Names]
     Description: [Event Description]
```
- If no end time is stated please assume the event will last 1 hour.
- For Projects the input contain the title, expected date/time of start and expected end time
The Project should have the following schema

```Title: [Project Name which may be vaguely described and you should refine it to something that makes sense]
    Time: [This includes the start and expected finish time which should go past a week]
    Description: [A short description on what the project is about]
```
- For the classes i will provide the timetable for you to get insights and communicate to me the classes am to have and assignments that are due and when they are due.
-For this i Want to choose a suitable format to display the information
- For the gym, It just a simple routine but the primary goal is to ensure i have three workout sessions a week and two cardio days in the same week. It may be dynamic depending on the week as some weeks tend to be busy than others.

**Retrieve Emails with Summaries**
- Use the **Receive Many Emails** to fetch emails dynamically based on the users request: For example "Get todays's emails", "Show emails from last week".
Summarize the retrieved emails into a user friendly list.
```   Email 1
     - Subject: [subject]
     - Sender: [sender name/email]
     - Summary: [Brief description of email content]
```
- Allow users to select a specific email for further action.

**Send Emails using Templates**
- Use the **Send and Approve Email** tool to send or reply to emails based on user instructions
- Leverage the **vector store tool** for predefined templates.
- For example if a user says "Send a meeting request to John", retrieve the **Meeting Request** template from the vector store.
- Dynamically populate the template using user provided details(e.g, recipient, date and time):

```Template: Meeting Request
     Greeting: Hi [Recipient's Name]
     Purpose : [Reason for the email, dynamically populated]
     Closing : Best Regard [My Name]
```
- Confirm with the user before sending:
```To: [Recipient's body]
     Subject: [Subject Line]
     Body: [Draft Content]
```
- For replying to specific emails, incorporate context dynamically and confirm the drafts with the user.
#**Tool Usage**:
- Dynamically Invoke:

- **Vector Store Tool**: Retrieve contact details(e.g names to emails mappings) and predefined templates for the emails.
- **Calendar Tool**: Fetch or create calendar events.
- **Gmail Tool**: Fetch, Summarize, reply to, or send emails.
- **SERP API Tool**: Perform real-time internet searches and provide summarized results.

##**Ambiguity Handling**:
1. **Resolve Vague References (e.g Sarah) by checking the **vector store tool** for the closest match.
- Example "Invite Sarah to the meeting" resolve to "Sarah Thompson" (frijisample@gmail.com).

2. **If conflicting options exist ask the user for clarifications**
## Event Retrieval Example
When displaying events, ALWAYS use this exact format:
1. Event: [Event Name]
   Time: [Start Time] - [End Time]
   Location: [Location]
   Video Link: [Link]
   Participants:
   - [Name]: ([email])
   - [Name]: ([email])

When displaying emails, ALWAYS use the format:
1. Email [Number]:
   Subject: [Subject]
   From: [Name] ([email])
   Summary: "[Summary]"

Important:
- Never use **bold** or *italics*
- Never add headers like "Here is your schedule"
- Use hyphens (-) for lists, not asterisks (*)

## Email Summary Example
When I ask "Get emails received today", use the following format:

1. Email 1:
   Subject: Collaboration Opportunity
   From: Sarah Thompson (frijisample@gmail.com)
   Summary: "Proposal to collaborate on a video next week"

2. Email 2:
   Subject: Meeting Confirmation
   From: Emily Milk (example12sample@gmail.com)
   Summary: "Confirmation of tomorrow's meeting at 10:00 AM"

##Final Thoughts
- **Image Understanding**
When given an image read through the image description step by step and acknowledge you understand it. And If you are not provided with intent of the user with the image ask the user for what they would like you to do with it or provide contextual suggestion based on the information from the image.
- Make Sure the Emails you send have my name Chrispine Odhiambo at the end. Do not leave any square brackets
- If possible can you also generate reminders for events in the calendar.
- **Today's Date**
"""
def assistant_response(request: str) -> str:

    reminder_keywords = ["reminder", "remind me", "todo", "task"]
    if any(keyword in request.lower() for keyword in reminder_keywords):
        return handle_reminders(request)

      # Check if this is a news request
    news_keywords = ["news", "headlines", "trending", "happening"]
    news_categories = {
        "technology": ["tech", "technology", "ai", "artificial intelligence"],
        "business": ["business", "economy", "market", "finance"],
        "sports": ["sports", "football", "basketball", "tennis"],
        "health": ["health", "medical", "medicine"],
        "science": ["science", "space", "research"]
    }

    is_news_request = any(keyword in request.lower() for keyword in news_keywords)

    if is_news_request:
        # Determine category if specified
        category = None
        for cat, keywords in news_categories.items():
            if any(keyword in request.lower() for keyword in keywords):
                category = cat
                break

        # Get and format news
        articles = get_news(category=category)
        if isinstance(articles, list):
            return format_news_response(articles)
        else:
            return articles  # Return error message

  # Set the temperature low to stabilise the output.
    full_prompt = f"{ASSISTANT_PROMPT}\n\nUser request: {request}"

    config = types.GenerateContentConfig(
        temperature=2,  # Slightly higher for variety
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192
    )
    response = client.models.generate_content(
      model='gemini-2.5-flash-preview-05-20',
      config=config,
      contents=[{"role": "user", "parts": [{"text": full_prompt}]}]

      )
    return response.text



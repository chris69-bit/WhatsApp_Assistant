# WhatsApp_Assistant
# Documentation for `assistant.py`

## Overview
This file implements a personal assistant system capable of managing calendar events, emails, reminders, and news retrieval. It integrates with Google APIs, News API, and other tools to provide seamless functionality for scheduling, communication, and information retrieval.

---

## Dependencies
The following libraries are imported and used in this file:
- `faiss`: For vector-based search and storage.
- `numpy`: For numerical operations.
- `requests`: For HTTP requests to external APIs.
- `enum`: For defining enumerations.
- `sqlite3`: For database operations.
- `datetime`, `timedelta`: For date and time manipulation.
- `base64`: For encoding email content.
- `dateparser`: For parsing natural language dates.
- `sentence_transformers`: For embedding sentences.
- `google.api_core.retry`: For retrying Google API calls.
- `genai`: For AI-based content generation.
- `googleapiclient.discovery`: For interacting with Google APIs.
- `google.auth.transport.requests`: For Google authentication.
- `os.path`: For file path operations.
- `json`: For JSON parsing and manipulation.

---

## Global Variables
- `client`: Instance of the GenAI client.
- `calendar_service`: Google Calendar API service.
- `gmail_service`: Google Gmail API service.
- `news_api_key`: API key for News API.

---

## Functions

### Initialization
#### `init_services(api_key, news_key, credentials)`
Initializes the services required for the assistant:
- `client`: GenAI client for AI-based operations.
- `calendar_service`: Google Calendar API service.
- `gmail_service`: Google Gmail API service.
- `news_api_key`: Stores the News API key.

---

### Calendar Management
#### `get_calendar_events(time_min=None, time_max=None, query=None)`
Fetches calendar events within a specified time range or matching a query.

#### `format_events(events)`
Formats a list of calendar events into a readable string.

#### `create_calendar_event(title, start_time, end_time=None, attendees=None, description="")`
Creates a new calendar event with the specified details.

---

### Email Management
#### `get_emails(query="", max_results=5)`
Fetches emails matching a query and limits the results to a specified number.

#### `format_email_summary(email)`
Formats an email's metadata into a readable summary.

#### `send_email(to, template_name, **kwargs)`
Sends an email using predefined templates and dynamically populates the content.

---

### Vector Store for Contacts
#### `ContactStore`
A class for managing contact information and performing vector-based searches.

- `add_contact(name, email)`: Adds a contact to the store.
- `find_email(name)`: Finds an email address by contact name.

---

### News Retrieval
#### `get_news(category=None, query=None, num_articles=5)`
Fetches news articles based on a category or query.

#### `format_news_response(articles)`
Formats a list of news articles into a readable string.

---

### Reminder Management
#### `init_db()`
Initializes the SQLite database for storing reminders.

#### `add_reminder_db(text, due_date, priority="medium")`
Adds a new reminder to the database.

#### `get_reminders_db(show_completed=False)`
Fetches reminders from the database, optionally including completed ones.

#### `complete_reminder_db(reminder_id)`
Marks a reminder as completed.

#### `delete_reminder_db(reminder_id)`
Deletes a reminder from the database.

#### `handle_reminders(request)`
Processes user requests related to reminders.

---

### Date Parsing
#### `parse_due_date(text)`
Parses natural language dates into ISO format.

---

### Assistant Response
#### `assistant_response(request: str) -> str`
Handles user requests and dynamically invokes the appropriate functionality:
- Calendar events
- Emails
- Reminders
- News retrieval

---

## Constants
### `EMAIL_TEMPLATES`
Predefined templates for sending emails. Example:
```python
{
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
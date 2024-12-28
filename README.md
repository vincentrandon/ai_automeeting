# AutoMeeting

AI-powered meeting scheduler that creates meetings in Notion and generates Google Meet links, integrated with Raycast.

## Setup

1. Clone the repository and set up the virtual environment:
   ```bash
   cd ~/Documents/Projets/automeeting
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Place your Google Calendar credentials in the `credentials/` directory:
   ```bash
   mkdir -p credentials
   # Copy your Google Calendar credentials JSON file here
   ```

3. Set up Raycast integration:
   ```bash
   # Create Raycast extensions directory
   mkdir -p ~/.raycast/extensions/automeeting
   
   # Copy the template script
   cp schedule_meeting.template.sh ~/.raycast/extensions/automeeting/schedule_meeting.sh
   
   # Make it executable
   chmod +x ~/.raycast/extensions/automeeting/schedule_meeting.sh
   ```

4. Configure your API keys:
   - Open `~/.raycast/extensions/automeeting/schedule_meeting.sh`
   - Replace the placeholder values with your actual API keys:
     ```bash
     export ANTHROPIC_API_KEY="your_anthropic_key"
     export NOTION_API_KEY="your_notion_key"
     export NOTION_DATABASE_ID="your_notion_database_id"
     export NOTION_CUSTOMERS_DATABASE_ID="your_customers_database_id"
     export NOTION_LEADS_DATABASE_ID="your_leads_database_id"
     ```

## Project Structure

```
automeeting/
├── main.py              # Main Python script
├── credentials/         # Google Calendar credentials
├── venv/               # Virtual environment
└── requirements.txt    # Python dependencies
```

## Usage

1. In Raycast, type "Schedule Meeting"
2. Enter your meeting details in natural language:
   - "First call with john@company.com tomorrow at 2pm"
   - "Schedule project review with jane@client.com next Monday at 10am"
   - "Réunion avec vincent@keerok.tech demain à 15h30"

The script will:
- Create a Google Meet link
- Schedule the meeting in your calendar
- Create a meeting notes page in Notion
- Link everything together

## Features

- 🌍 Bilingual support (English/French)
- 📅 Natural language date/time parsing
- 🔍 Automatic company detection
- 📝 Meeting notes templates
- 🤖 AI-powered meeting context understanding
- 🔄 Automatic follow-up task creation

## Troubleshooting

If you encounter issues:
1. Check that your virtual environment is activated
2. Verify your API keys are correctly set
3. Ensure your Google Calendar credentials are in place
4. Check the paths in `schedule_meeting.sh` match your setup

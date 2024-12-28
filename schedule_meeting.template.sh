#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Schedule Meeting
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 📅
# @raycast.packageName AutoMeeting
# @raycast.argument1 { "type": "text", "placeholder": "Meeting details (e.g., 'First call with john@company.com tomorrow at 2pm')" }

# Documentation:
# @raycast.author Vincent Randon
# @raycast.authorURL https://github.com/vincentrandon

# Check if meeting details are provided
if [ -z "$1" ]; then
  echo "❌ Please provide meeting details"
  exit 1
fi

# Set project directory and activate virtual environment
PROJECT_DIR="$HOME/Documents/your_project_directory"
VENV_DIR="$HOME/Documents/your_virtual_environment_directory"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Set Python path to include project directory
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Set environment variables
export ANTHROPIC_API_KEY="your_anthropic_key"
export NOTION_API_KEY="your_notion_key"
export NOTION_DATABASE_ID="your_notion_database_id"
export NOTION_CUSTOMERS_DATABASE_ID="your_customers_database_id"
export NOTION_LEADS_DATABASE_ID="your_leads_database_id"
export GOOGLE_CREDENTIALS_FILE="$PROJECT_DIR/credentials/your_google_credentials.json"

# Run the Python script with the meeting details
python3 - << EOF
import sys
import os
from main import MeetingScheduler, ValidationError

def run_scheduler(meeting_request: str) -> None:
    try:
        # Initialize scheduler in non-interactive mode for Raycast
        scheduler = MeetingScheduler(interactive=False)
        
        # Process the meeting request
        result = scheduler.process_meeting_request(meeting_request)
        
        # Format success message for Raycast
        print(f"✅ Meeting scheduled successfully!")
        print(f"📅 {result['meeting_info']['title']}")
        print(f"🔗 Meet: {result['meet_link']}")
        print(f"📝 Notion: https://notion.so/{result['notion_page_id'].replace('-', '')}")
        
        if result['company_info']:
            print(f"👥 Found as {result['company_info']['type']}")
        
        sys.exit(0)
    except ValidationError as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)

meeting_request = """$1"""
run_scheduler(meeting_request)
EOF 
# AutoMeeting

AI-powered meeting scheduler that creates meetings in Notion and generates Google Meet links, integrated with Raycast.

## Features

- 🌍 Bilingual support (English/French)
- 📅 Natural language date/time parsing
- 🔍 Automatic company detection
- 📝 Meeting notes templates in Notion
- 🤖 AI-powered meeting context understanding
- 🔄 Automatic follow-up task creation

## Prerequisites

- Python 3.12+
- A Google Cloud Platform account
- A Notion account with API access
- An Anthropic account (for Claude API)
- Raycast (for macOS integration)

## Setup Instructions

### 1. Python Environment Setup

```bash
# Clone the repository
git clone [your-repo-url]
cd automeeting

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Google Calendar API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the Google Calendar API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"
4. Configure OAuth consent screen:
   - Go to "APIs & Services" > "OAuth consent screen"
   - Choose "External" user type
   - Fill in the application name and user support email
   - Add the following scopes:
     * `https://www.googleapis.com/auth/calendar`
     * `https://www.googleapis.com/auth/calendar.events`
     * `https://www.googleapis.com/auth/calendar.readonly`
   - Add your email as a test user
5. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop application"
   - Download the JSON file
6. Save the credentials:
   ```bash
   mkdir -p credentials
   # Move the downloaded JSON file to credentials/ directory
   mv ~/Downloads/client_secret_*.json credentials/
   ```

### 3. Notion Setup

1. Go to [Notion Developers](https://developers.notion.com)
2. Create a new integration
3. Copy the API key
4. Share your Notion databases with the integration:
   - Open each database in Notion
   - Click "Share" and invite your integration

### 4. Environment Configuration

1. Copy the template script:
```bash
cp schedule_meeting.template.sh schedule_meeting.sh
chmod +x schedule_meeting.sh
```

2. Edit `schedule_meeting.sh` with your API keys and paths:
```bash
export ANTHROPIC_API_KEY="your_anthropic_key"
export NOTION_API_KEY="your_notion_key"
export NOTION_DATABASE_ID="your_notion_database_id"
export NOTION_CUSTOMERS_DATABASE_ID="your_customers_database_id"
export NOTION_LEADS_DATABASE_ID="your_leads_database_id"
export GOOGLE_CREDENTIALS_FILE="$PROJECT_DIR/credentials/your_google_credentials.json"
```

### 5. First Run and OAuth Authentication

1. Run the script for the first time:
```bash
python main.py
```

2. A browser window will open for Google OAuth:
   - Sign in with your Google account
   - Grant the requested permissions
   - This will create a `token.pickle` file that stores permanent credentials

### 6. Raycast Integration (Optional)

1. Create Raycast extensions directory:
```bash
mkdir -p ~/.raycast/extensions/automeeting
```

2. Copy and configure the script:
```bash
cp schedule_meeting.sh ~/.raycast/extensions/automeeting/
```

## Usage

### Command Line

```bash
source venv/bin/activate
python main.py
```

Then enter your meeting request in English or French:
- "Schedule a call with john@company.com tomorrow at 2pm"
- "Réunion avec marie@entreprise.fr lundi prochain à 10h"

### Via Raycast

1. Press `⌘ + Space` to open Raycast
2. Type "Schedule Meeting"
3. Enter your meeting details in natural language

## Troubleshooting

### Token Issues

If you encounter token errors:
1. Delete the existing token:
   ```bash
   rm token.pickle
   ```
2. Run the script again to trigger a new OAuth flow
3. Follow the browser prompts to authenticate

### Common Issues

1. **"Missing required environment variables"**
   - Check all environment variables are set in `schedule_meeting.sh`
   - Ensure the script is sourced properly

2. **"Invalid Grant"**
   - Delete `token.pickle` and re-authenticate
   - Check that your OAuth consent screen is properly configured

3. **"Access Denied"**
   - Verify your email is added as a test user in GCP
   - Check that all required scopes are enabled

## Logs

Check `meeting_scheduler.log` for detailed debugging information.

## Contributing

Feel free to submit issues and pull requests.

## License

MIT

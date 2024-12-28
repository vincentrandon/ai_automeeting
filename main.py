import os
from anthropic import Anthropic
from notion_client import Client
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import datetime
import json
import re
from langdetect import detect
import logging
import sys
import zoneinfo
from typing import Optional, Dict, Any


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('meeting_scheduler.log')
    ]
)

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

class MeetingScheduler:
    DEFAULT_DURATION = 30  # minutes
    REQUIRED_ENV_VARS = [
        'ANTHROPIC_API_KEY',
        'NOTION_API_KEY',
        'NOTION_DATABASE_ID',
        'NOTION_CUSTOMERS_DATABASE_ID',
        'NOTION_LEADS_DATABASE_ID',
        'GOOGLE_CREDENTIALS_FILE'
    ]

    def __init__(self, interactive: bool = True):
        logger.info("Initializing MeetingScheduler")
        self.interactive = interactive
        self.validate_environment()
        
        self.anthropic = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        self.notion = Client(auth=os.environ.get('NOTION_API_KEY'))
        self.notion_database_id = os.environ.get('NOTION_DATABASE_ID')
        self.customers_database_id = os.environ.get('NOTION_CUSTOMERS_DATABASE_ID')
        self.leads_database_id = os.environ.get('NOTION_LEADS_DATABASE_ID')
        self.google_service = self._setup_google_calendar()

    def validate_environment(self):
        """Validate all required environment variables are set."""
        logger.info("Validating environment variables")
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not os.environ.get(var)]
        if missing_vars:
            raise ValidationError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _setup_google_calendar(self):
        """Set up Google Calendar API connection."""
        logger.info("Setting up Google Calendar connection")
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = None
        
        if os.path.exists('token.pickle'):
            logger.info("Loading existing Google Calendar credentials from token.pickle")
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            logger.info("Refreshing Google Calendar credentials")
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                logger.info("Initiating new Google Calendar authentication flow")
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.environ.get('GOOGLE_CREDENTIALS_FILE'), SCOPES)
                creds = flow.run_local_server(port=0)
            
            logger.info("Saving new credentials to token.pickle")
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return build('calendar', 'v3', credentials=creds)

    def validate_meeting_info(self, meeting_info: Dict[str, Any]) -> None:
        """Validate meeting information."""
        required_fields = ['title', 'datetime', 'attendee_email']
        missing_fields = [field for field in required_fields if not meeting_info.get(field)]
        
        if missing_fields:
            raise ValidationError(f"Missing required meeting information: {', '.join(missing_fields)}")
        
        # Validate email format
        email = meeting_info['attendee_email']
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValidationError(f"Invalid email format: {email}")
        
        # Validate datetime
        try:
            datetime.datetime.fromisoformat(meeting_info['datetime'])
        except ValueError as e:
            raise ValidationError(f"Invalid datetime format: {str(e)}")

    def should_create_company(self, company_name: str, email: str, lang: str) -> bool:
        """Ask Claude whether to create a new company/lead entry."""
        if not self.interactive:
            return False
            
        system_prompt = """You are a business development assistant. 
        Based on the company information provided, decide if we should create a new lead in our database.
        Consider:
        - Is this likely a real company?
        - Does the email domain match the company name?
        - Is this a business email (not gmail, hotmail, etc.)?
        
        Respond with a JSON containing:
        {
            "should_create": boolean,
            "reason": string,
            "suggested_type": "customer" or "lead"
        }
        """
        
        try:
            message = self.anthropic.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Company: {company_name}\nEmail: {email}"}
                ]
            )
            
            result = json.loads(message.content[0].text)
            logger.info(f"Company creation recommendation: {result}")
            
            if result['should_create']:
                # Ask for user confirmation
                question = (
                    f"\nSuggestion de créer un nouveau {result['suggested_type']}: {company_name}"
                    if lang == 'fr' else
                    f"\nSuggestion to create a new {result['suggested_type']}: {company_name}"
                )
                reason = (
                    f"Raison: {result['reason']}"
                    if lang == 'fr' else
                    f"Reason: {result['reason']}"
                )
                confirm = (
                    "Voulez-vous créer l'entrée ? (oui/non): "
                    if lang == 'fr' else
                    "Would you like to create the entry? (yes/no): "
                )
                
                print(f"{question}\n{reason}")
                response = input(confirm).lower()
                return response in ['yes', 'oui', 'y', 'o']
            
            return False
            
        except Exception as e:
            logger.error(f"Error in company creation decision: {str(e)}")
            return False

    def create_company_entry(self, company_name: str, email: str, entry_type: str) -> Optional[Dict]:
        """Create a new company or lead entry in Notion."""
        try:
            database_id = (
                self.customers_database_id if entry_type == 'customer'
                else self.leads_database_id
            )
            
            # Use the correct property name based on entry type
            name_property = "Company name" if entry_type == 'customer' else "Lead name"
            properties = {
                name_property: {"title": [{"text": {"content": company_name}}]},
                "Status": {"select": {"name": "New"}},
            }
            
            new_entry = self.notion.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
            
            logger.info(f"Created new {entry_type} entry: {company_name}")
            return {'type': entry_type, 'data': new_entry}
            
        except Exception as e:
            logger.error(f"Error creating {entry_type} entry: {str(e)}")
            return None

    def process_meeting_request(self, user_request: str) -> Dict[str, Any]:
        """Process a meeting request with validation and company handling."""
        logger.info(f"Processing meeting request: {user_request}")
        
        # Detect language
        lang = detect(user_request)
        logger.info(f"Detected language: {lang}")
        
        try:
            # Get initial meeting details from Claude
            meeting_info = self._get_meeting_details(user_request, lang)
            
            # Check for missing required information
            required_fields = ['title', 'datetime', 'attendee_email']
            missing_fields = [field for field in required_fields if not meeting_info.get(field)]
            
            if missing_fields and self.interactive:
                logger.info(f"Missing information: {missing_fields}")
                # Get missing information interactively
                additional_info = self._get_missing_info(lang, meeting_info)
                meeting_info.update(additional_info)
            elif missing_fields:
                raise ValidationError(f"Missing required information: {', '.join(missing_fields)}")
            
            # Validate the complete information
            self.validate_meeting_info(meeting_info)
            
            # Extract company name from email if not provided
            company_name = meeting_info.get('company_name') or self.extract_company_from_email(meeting_info['attendee_email'])
            
            # Look up company in databases
            company_info = self.find_company_in_database(company_name, meeting_info['attendee_email'])
            
            # If company not found and in interactive mode, ask about creating it
            if not company_info and self.interactive:
                if lang == 'fr':
                    print(f"\nEntreprise '{company_name}' non trouvée dans la base de données.")
                    create = input("Voulez-vous créer une nouvelle entrée ? (oui/non): ").lower()
                    if create in ['oui', 'o']:
                        type_choice = input("Est-ce un client ou un lead ? (client/lead): ").lower()
                        entry_type = 'customer' if type_choice == 'client' else 'lead'
                else:
                    print(f"\nCompany '{company_name}' not found in database.")
                    create = input("Would you like to create a new entry? (yes/no): ").lower()
                    if create in ['yes', 'y']:
                        type_choice = input("Is this a customer or a lead? (customer/lead): ").lower()
                        entry_type = type_choice
                
                if create in ['yes', 'y', 'oui', 'o']:
                    company_info = self.create_company_entry(company_name, meeting_info['attendee_email'], entry_type)
            
            # Create calendar event and notion page
            result = self._create_meeting_entries(meeting_info, company_info, lang)
            
            return {
                "meet_link": result["meet_link"],
                "notion_page_id": result["notion_page_id"],
                "meeting_info": meeting_info,
                "company_info": company_info,
                "language": lang
            }
            
        except Exception as e:
            logger.error(f"Error in process_meeting_request: {str(e)}")
            raise ValidationError(
                f"Erreur lors du traitement: {str(e)}" if lang == 'fr' else
                f"Error during processing: {str(e)}"
            )

    def _get_meeting_details(self, user_request: str, lang: str) -> Dict[str, Any]:
        """Get meeting details from Claude with proper error handling."""
        paris_tz = zoneinfo.ZoneInfo("Europe/Paris")
        current_date = datetime.datetime.now(paris_tz)
        tomorrow = current_date + datetime.timedelta(days=1)
        
        system_prompt = """You are a bilingual (French/English) meeting scheduler assistant. Extract the following information from the meeting request:
        - Meeting title / Titre de la réunion
        - Description/agenda / Description/ordre du jour
        - Date and time / Date et heure
        - Duration (in minutes) / Durée (en minutes)
        - Attendee email / Email du participant
        - Company name (if specified explicitly) / Nom de l'entreprise (si spécifié explicitement)
        
        Format your response as JSON with these exact keys: title, description, datetime, duration, attendee_email, company_name
        
        IMPORTANT:
        - If no explicit title is given, set title to "Meeting" (or "Réunion" in French)
        - If company name is not explicitly specified, set it to null
        - If duration is not specified, set it to 30 (default duration)
        - Extract email addresses even if they are at the end of the sentence
        - Always include any email address found in the text in attendee_email
        
        The input may be in French or English. Process it accordingly but always return the JSON with the same keys.
        For datetime, ALWAYS return in ISO format with the Europe/Paris timezone offset.
        
        IMPORTANT TIME HANDLING:
        - Current time in Paris: {current_date}
        - For "tomorrow"/"demain", use this date: {tomorrow_date}
        - Times must be EXACTLY as specified, with NO adjustments:
          * When user says "14h30" → it must be exactly 14:30 Paris time
          * When user says "9h" → it must be exactly 09:00 Paris time
          * When user says "2pm" → it must be exactly 14:00 Paris time
        - DO NOT perform any timezone conversions
        - DO NOT adjust the time in any way
        - The time in the response should be EXACTLY what the user specified
        
        Examples:
        1. Input: "Réunion demain à 14h30 avec vincent@keerok.tech"
        -> Must return: {{
            "title": "Réunion",
            "description": null,
            "datetime": "{tomorrow_date}T14:30:00+02:00",
            "duration": 30,
            "attendee_email": "vincent@keerok.tech",
            "company_name": null
        }}
        """.format(
            current_date=current_date.strftime("%Y-%m-%d %H:%M:%S %Z"),
            tomorrow_date=tomorrow.strftime("%Y-%m-%d")
        )
        
        try:
            message = self.anthropic.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_request}
                ]
            )
            
            logger.info(f"Claude response: {message.content[0].text}")
            meeting_info = json.loads(message.content[0].text)
            
            # Parse and validate the datetime
            dt = datetime.datetime.fromisoformat(meeting_info['datetime'])
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=paris_tz)
            
            # Log the original and processed times for debugging
            logger.info(f"Original datetime from request: {meeting_info['datetime']}")
            logger.info(f"Processed datetime: {dt.isoformat()}")
            
            # Update the datetime in the meeting_info
            meeting_info['datetime'] = dt.isoformat()
            
            # Set duration if not specified
            meeting_info['duration'] = int(meeting_info.get('duration', self.DEFAULT_DURATION))
            
            return meeting_info
            
        except Exception as e:
            error_msg = (
                f"Erreur lors de l'analyse de la demande: {str(e)}"
                if lang == 'fr' else
                f"Error parsing meeting request: {str(e)}"
            )
            raise ValidationError(error_msg)

    def _handle_company_info(self, meeting_info: Dict[str, Any], lang: str) -> Optional[Dict]:
        """Handle company information with creation if needed."""
        company_name = meeting_info.get('company_name') or self.extract_company_from_email(meeting_info['attendee_email'])
        company_info = self.find_company_in_database(company_name, meeting_info['attendee_email'])
        
        if not company_info and self.should_create_company(company_name, meeting_info['attendee_email'], lang):
            entry_type = 'lead'  # Default to lead for new entries
            company_info = self.create_company_entry(company_name, meeting_info['attendee_email'], entry_type)
        
        return company_info

    def _create_meeting_entries(self, meeting_info: Dict[str, Any], company_info: Optional[Dict], lang: str) -> Dict[str, Any]:
        """Create calendar event and notion page with proper error handling."""
        try:
            # Set up the meeting time
            start_time = datetime.datetime.fromisoformat(meeting_info['datetime'])
            if not start_time.tzinfo:
                paris_tz = zoneinfo.ZoneInfo("Europe/Paris")
                start_time = start_time.replace(tzinfo=paris_tz)
            
            # Extract company name from email if not provided in meeting_info
            company_name = (
                meeting_info.get('company_name') or 
                self.extract_company_from_email(meeting_info['attendee_email'])
            )
            
            # Get company name for display
            display_company_name = self.get_company_name_from_info(company_info) or company_name
            
            # Create Google Meet link
            meet_link = self.create_meet_link(
                meeting_info['title'],
                start_time,
                meeting_info['duration'],
                meeting_info['attendee_email'],
                display_company_name
            )
            
            # Create Notion page
            notion_page = self.create_meeting_notes_page(
                meeting_info['title'],
                company_info,
                start_time
            )
            
            # Update with Meet link
            self.notion.pages.update(
                page_id=notion_page['id'],
                properties={
                    "Google Meet": {"url": meet_link}
                }
            )
            
            return {
                "meet_link": meet_link,
                "notion_page_id": notion_page["id"]
            }
            
        except Exception as e:
            error_msg = (
                f"Erreur lors de la création des entrées: {str(e)}"
                if lang == 'fr' else
                f"Error creating meeting entries: {str(e)}"
            )
            raise ValidationError(error_msg)

    def extract_company_from_email(self, email: str) -> str:
        """Extract company name from email domain."""
        domain = email.split('@')[1]
        # Get both full domain and first part
        company_full = domain.capitalize()
        company_name = domain.split('.')[0].capitalize()
        logger.info(f"Extracted company names: full='{company_full}', name='{company_name}'")
        return company_name

    def find_company_in_database(self, company_name: str, email: str) -> Optional[Dict]:
        """Search for company in both customers and leads databases."""
        # Try different variations of the company name
        company_variations = [
            company_name,  # Original name
            company_name.lower(),  # Lowercase
            company_name.upper(),  # Uppercase
            email.split('@')[1].split('.')[0].capitalize(),  # Just domain name
            email.split('@')[1].capitalize(),  # Full domain
        ]
        logger.info(f"Searching for company variations: {company_variations}")
        
        # Search in customers database
        logger.info("Searching in customers database")
        try:
            customer_results = self.notion.databases.query(
                database_id=self.customers_database_id,
                filter={
                    "or": [
                        {
                            "property": "Company name",
                            "title": {
                                "contains": variation
                            }
                        } for variation in company_variations
                    ]
                }
            ).get('results', [])
            
            if customer_results:
                found_name = self.get_company_name_from_info({'type': 'customer', 'data': customer_results[0]})
                logger.info(f"Found company in customers database: {found_name}")
                return {'type': 'customer', 'data': customer_results[0]}
        except Exception as e:
            logger.error(f"Error searching customers database: {str(e)}")

        # Search in leads database
        logger.info("Searching in leads database")
        try:
            lead_results = self.notion.databases.query(
                database_id=self.leads_database_id,
                filter={
                    "or": [
                        {
                            "property": "Lead name",
                            "title": {
                                "contains": variation
                            }
                        } for variation in company_variations
                    ]
                }
            ).get('results', [])
            
            if lead_results:
                found_name = self.get_company_name_from_info({'type': 'lead', 'data': lead_results[0]})
                logger.info(f"Found company in leads database: {found_name}")
                return {'type': 'lead', 'data': lead_results[0]}
        except Exception as e:
            logger.error(f"Error searching leads database: {str(e)}")

        logger.warning(f"Company not found in any database for variations: {company_variations}")
        return None

    def get_company_name_from_info(self, company_info: Optional[Dict]) -> Optional[str]:
        """Extract company name from company_info."""
        if not company_info:
            return None
        
        try:
            # Use correct property names for each type
            property_name = "Company name" if company_info['type'] == 'customer' else "Lead name"
            return company_info['data']['properties'][property_name]['title'][0]['text']['content']
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting company name from info: {str(e)}")
            return None

    def create_meeting_notes_page(self, title: str, company_info: Optional[Dict], date: datetime.datetime) -> Dict:
        """Create a new page for meeting notes using the template."""
        company_name = self.get_company_name_from_info(company_info) or title
        meeting_title = f"Meeting with {company_name}"
        logger.info(f"Creating meeting notes page with title: {meeting_title}")
        
        properties = {
            "Name": {"title": [{"text": {"content": meeting_title}}]},
            "Status": {"select": {"name": "Planned"}},
            "Meeting date": {"date": {"start": date.isoformat()}}
        }

        # Link to customer/lead if found
        if company_info:
            relation_key = "Customer" if company_info['type'] == 'customer' else "Lead"
            properties[relation_key] = {
                "relation": [{"id": company_info['data']['id']}]
            }
            logger.info(f"Linking meeting to {company_info['type']}: {company_info['data']['id']}")

        try:
            # Create page from template
            new_page = self.notion.pages.create(
                parent={"database_id": self.notion_database_id},
                properties=properties,
                template={"page_id": "16ab7bf5342f80c28c33d71950b93bcc"}  # Your template ID
            )
            logger.info(f"Created Notion page with ID: {new_page['id']}")
            return new_page
        except Exception as e:
            logger.error(f"Error creating Notion page: {str(e)}")
            raise

    def create_meet_link(self, summary: str, start_time: datetime.datetime, duration_minutes: int, attendee_email: str, company_name: Optional[str] = None) -> str:
        """Create Google Meet link with formatted title."""
        meet_title = f"{company_name or 'Meeting'} <> Vincent"
        logger.info(f"Creating Google Meet link with title: {meet_title}")
        
        # Ensure we're using the exact time provided
        if not start_time.tzinfo:
            paris_tz = zoneinfo.ZoneInfo("Europe/Paris")
            start_time = start_time.replace(tzinfo=paris_tz)
        
        # Log the exact time being used
        logger.info(f"Creating meeting at exactly: {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        event = {
            'summary': meet_title,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Europe/Paris',
            },
            'end': {
                'dateTime': (start_time + datetime.timedelta(minutes=duration_minutes)).isoformat(),
                'timeZone': 'Europe/Paris',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"meeting_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            },
            'attendees': [
                {'email': attendee_email}
            ]
        }

        try:
            event = self.google_service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()
            
            meet_link = event.get('hangoutLink')
            logger.info(f"Created Google Meet link: {meet_link}")
            
            # Log the actual event time from Google Calendar
            created_start_time = datetime.datetime.fromisoformat(event['start']['dateTime'])
            logger.info(f"Confirmed meeting time in calendar: {created_start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            return meet_link
        except Exception as e:
            logger.error(f"Error creating Google Meet event: {str(e)}")
            raise

    def _get_missing_info(self, lang: str, meeting_info: Dict[str, Any]) -> Dict[str, Any]:
        """Interactively gather missing meeting information."""
        info = {}
        
        if lang == 'fr':
            email_prompt = "Quel est l'email du participant ? "
            title_prompt = "Quel est le titre de la réunion ? "
        else:
            email_prompt = "What is the attendee's email? "
            title_prompt = "What is the meeting title? "
        
        # Only ask for email if it's not already in meeting_info
        if 'attendee_email' not in meeting_info:
            while 'attendee_email' not in info:
                email = input(email_prompt).strip()
                if re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    info['attendee_email'] = email
                else:
                    print("Invalid email format. Please try again." if lang == 'en' else "Format d'email invalide. Veuillez réessayer.")
        
        # Get title if missing
        if 'title' not in meeting_info or not meeting_info['title']:
            title = input(title_prompt).strip()
            if title:
                info['title'] = title
            else:
                # Default title if none provided
                company = meeting_info.get('company_name') or self.extract_company_from_email(meeting_info['attendee_email'])
                info['title'] = f"Meeting with {company}" if lang == 'en' else f"Réunion avec {company}"
            
        return info

def main():
    """Main function with error handling."""
    logger.info("Starting meeting scheduler")
    
    try:
        scheduler = MeetingScheduler(interactive=True)
    except ValidationError as e:
        logger.error(f"Initialization error: {str(e)}")
        print(f"\nError: {str(e)}")
        return
    
    print("Please describe the meeting you want to schedule (in English or French):")
    print("Veuillez décrire la réunion que vous souhaitez planifier (en anglais ou en français) :")
    meeting_request = input()
    
    try:
        result = scheduler.process_meeting_request(meeting_request)
        display_results(result)
    except ValidationError as e:
        logger.error(f"Processing error: {str(e)}")
        print(f"\nError: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        print("\nAn unexpected error occurred. Please check the logs for details.")

def display_results(result: Dict[str, Any]) -> None:
    """Display results in the appropriate language."""
    if result['language'] == 'fr':
        logger.info("Displaying French success message")
        print("\nRéunion planifiée avec succès !")
        print(f"Lien Google Meet : {result['meet_link']}")
        print(f"ID de la page Notion : {result['notion_page_id']}")
        print("\nDétails de la réunion :")
        for key, value in result['meeting_info'].items():
            print(f"{key}: {value}")
        
        if result['company_info']:
            print(f"\nEntreprise trouvée dans la base de données {result['company_info']['type']} !")
        else:
            print("\nAttention : Entreprise non trouvée dans les bases de données")
    else:
        logger.info("Displaying English success message")
        print("\nMeeting scheduled successfully!")
        print(f"Google Meet link: {result['meet_link']}")
        print(f"Notion page ID: {result['notion_page_id']}")
        print("\nMeeting details:")
        for key, value in result['meeting_info'].items():
            print(f"{key}: {value}")
        
        if result['company_info']:
            print(f"\nCompany found in {result['company_info']['type']} database!")
        else:
            print("\nWarning: Company not found in databases")

if __name__ == "__main__":
    main()

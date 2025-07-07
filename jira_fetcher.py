#!/usr/bin/env python3
"""
Jira Ticket Fetcher
Fetches tickets from Jira and saves them locally for analysis.
Logs all requests and responses.
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime
from typing import List, Dict, Any
from tabulate import tabulate
from colorama import init, Fore, Style
from dotenv import load_dotenv

# Initialize colorama for colored output
init()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('jira_requests.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class JiraTicketFetcher:
    # Single JQL query definition - modify this to change what tickets are fetched
    DEFAULT_JQL = "project = L2 AND updated >= -300d ORDER BY updated DESC"
    
    def __init__(self):
        load_dotenv()
        self.jira_url = os.getenv('JIRA_URL')
        self.jira_username = os.getenv('JIRA_USERNAME')
        self.jira_token = os.getenv('JIRA_TOKEN')
        
        if not all([self.jira_url, self.jira_username, self.jira_token]):
            self.setup_credentials()
    
    def setup_credentials(self):
        """Setup Jira credentials interactively"""
        print(f"{Fore.YELLOW}Setting up Jira credentials...{Style.RESET_ALL}")
        print("You can also create a .env file with these variables:")
        print("JIRA_URL=https://your-company.atlassian.net")
        print("JIRA_USERNAME=your-email@company.com")
        print("JIRA_TOKEN=your-api-token")
        print()
        
        self.jira_url = input("Enter your Jira URL (e.g., https://company.atlassian.net): ").strip()
        self.jira_username = input("Enter your Jira username/email: ").strip()
        self.jira_token = input("Enter your Jira API token: ").strip()
        
        # Save to .env file
        with open('.env', 'w') as f:
            f.write(f"JIRA_URL={self.jira_url}\n")
            f.write(f"JIRA_USERNAME={self.jira_username}\n")
            f.write(f"JIRA_TOKEN={self.jira_token}\n")
        
        print(f"{Fore.GREEN}Credentials saved to .env file{Style.RESET_ALL}")
    
    def test_jira_connection(self) -> bool:
        """Test connection to Jira"""
        try:
            logger.info("Testing Jira connection...")
            response = requests.get(
                f"{self.jira_url}/rest/api/2/myself",
                auth=(self.jira_username, self.jira_token),
                timeout=10
            )
            
            logger.info(f"Connection test status: {response.status_code}")
            
            if response.status_code == 200:
                user_info = response.json()
                logger.info(f"Connected as: {user_info.get('displayName', 'Unknown')}")
                print(f"{Fore.GREEN}✓ Connected to Jira as {user_info.get('displayName', 'Unknown')}{Style.RESET_ALL}")
                return True
            else:
                logger.error(f"Jira connection failed: {response.status_code}")
                print(f"{Fore.RED}✗ Jira connection failed: {response.status_code}{Style.RESET_ALL}")
                return False
        except Exception as e:
            logger.error(f"Jira connection error: {str(e)}")
            print(f"{Fore.RED}✗ Jira connection error: {str(e)}{Style.RESET_ALL}")
            return False
    
    def fetch_tickets(self, max_results: int = None) -> List[Dict]:
        """Fetch tickets from Jira using the predefined JQL query with pagination"""
        jql = self.DEFAULT_JQL
        
        # Log the request
        logger.info(f"Fetching Jira tickets with JQL: {jql}")
        logger.info(f"Max results requested: {max_results if max_results else 'ALL'}")
        logger.info(f"Jira URL: {self.jira_url}")
        
        all_tickets = []
        start_at = 0
        batch_size = 100  # Use smaller batch size for pagination
        total_available = None
        
        try:
            while True:
                url = f"{self.jira_url}/rest/api/2/search"
                params = {
                    'jql': jql,
                    'maxResults': batch_size,
                    'startAt': start_at,
                    'fields': 'key,summary,description,status,priority,assignee,reporter,created,updated,issuetype,components,labels,comment,changelog',
                    'expand': 'changelog'
                }
                
                logger.info(f"Making paginated request - batch {len(all_tickets)//batch_size + 1}")
                logger.info(f"Request parameters: {params}")
                
                response = requests.get(
                    url,
                    auth=(self.jira_username, self.jira_token),
                    params=params,
                    timeout=30
                )
                
                logger.info(f"Response status code: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch tickets: HTTP {response.status_code}")
                    logger.error(f"Response text: {response.text}")
                    print(f"{Fore.RED}✗ Failed to fetch tickets: {response.status_code}{Style.RESET_ALL}")
                    break
                
                data = response.json()
                batch_tickets = data.get('issues', [])
                total_available = data.get('total', 0)
                
                # Log batch information
                logger.info(f"Batch fetched: {len(batch_tickets)} tickets")
                logger.info(f"Total available: {total_available}")
                logger.info(f"Current start index: {data.get('startAt', 0)}")
                
                if not batch_tickets:
                    logger.info("No more tickets to fetch")
                    break
                
                all_tickets.extend(batch_tickets)
                
                # Show progress
                print(f"{Fore.YELLOW}📦 Fetched {len(all_tickets)}/{total_available} tickets...{Style.RESET_ALL}")
                
                # Check if we've reached the user's limit
                if max_results and len(all_tickets) >= max_results:
                    all_tickets = all_tickets[:max_results]
                    logger.info(f"Reached user-specified limit of {max_results} tickets")
                    break
                
                # Check if we've fetched all available tickets
                if len(all_tickets) >= total_available:
                    logger.info("Fetched all available tickets")
                    break
                
                # Prepare for next batch
                start_at += batch_size
            
            logger.info(f"Successfully fetched {len(all_tickets)} tickets total")
            print(f"{Fore.GREEN}✓ Fetched {len(all_tickets)} tickets total{Style.RESET_ALL}")
            
            if total_available and len(all_tickets) < total_available:
                remaining = total_available - len(all_tickets)
                print(f"{Fore.CYAN}ℹ️  {remaining} more tickets available (use larger max_results to fetch more){Style.RESET_ALL}")
            
            return all_tickets
                
        except Exception as e:
            logger.error(f"Exception while fetching tickets: {str(e)}")
            print(f"{Fore.RED}✗ Error fetching tickets: {str(e)}{Style.RESET_ALL}")
            return all_tickets if all_tickets else []
    
    def save_tickets_to_json(self, tickets: List[Dict], filename: str = None) -> str:
        """Save tickets to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jira_tickets_{timestamp}.json"
        
        try:
            # Prepare data for saving
            data = {
                'fetch_timestamp': datetime.now().isoformat(),
                'jql_query': self.DEFAULT_JQL,
                'total_tickets': len(tickets),
                'tickets': tickets
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Tickets saved to: {filename}")
            print(f"{Fore.GREEN}✓ Tickets saved to {filename}{Style.RESET_ALL}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save tickets: {str(e)}")
            print(f"{Fore.RED}✗ Failed to save tickets: {str(e)}{Style.RESET_ALL}")
            return ""
    
    def display_ticket_summary(self, tickets: List[Dict]):
        """Display a summary table of tickets"""
        if not tickets:
            print(f"{Fore.YELLOW}No tickets to display{Style.RESET_ALL}")
            return
        
        table_data = []
        for ticket in tickets:
            fields = ticket['fields']
            
            key = ticket['key']
            summary = fields.get('summary', '')[:50] + "..." if len(fields.get('summary', '')) > 50 else fields.get('summary', '')
            status = fields.get('status', {}).get('name', 'Unknown')
            priority = fields.get('priority', {}).get('name', 'Unknown')
            assignee = fields.get('assignee')
            assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
            updated = fields.get('updated', '')[:10]
            
            table_data.append([key, summary, status, priority, assignee_name, updated])
        
        headers = ['Key', 'Summary', 'Status', 'Priority', 'Assignee', 'Updated']
        print(f"\n{Fore.CYAN}Ticket Overview:{Style.RESET_ALL}")
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
    
    def run(self):
        """Main execution method"""
        print(f"{Fore.CYAN}🎫 Jira Ticket Fetcher{Style.RESET_ALL}")
        print("=" * 40)
        
        # Test connection
        if not self.test_jira_connection():
            logger.error("Failed to connect to Jira. Exiting.")
            return
        
        # Get max results
        print(f"\n{Fore.CYAN}How many tickets to fetch?{Style.RESET_ALL}")
        print("  - Enter a number (e.g., 500)")
        print("  - Press Enter for ALL available tickets")
        print("  - The system will use pagination to bypass server limits")
        
        try:
            user_input = input(f"\n{Fore.YELLOW}Max tickets (or Enter for ALL): {Style.RESET_ALL}").strip()
            if user_input:
                max_results = int(user_input)
                print(f"{Fore.CYAN}Will fetch up to {max_results} tickets{Style.RESET_ALL}")
            else:
                max_results = None
                print(f"{Fore.CYAN}Will fetch ALL available tickets{Style.RESET_ALL}")
        except ValueError:
            max_results = None
            print(f"{Fore.YELLOW}Invalid input, will fetch ALL available tickets{Style.RESET_ALL}")
        
        # Fetch tickets
        print(f"\n{Fore.YELLOW}Fetching tickets...{Style.RESET_ALL}")
        tickets = self.fetch_tickets(max_results)
        
        if tickets:
            # Display summary
            self.display_ticket_summary(tickets)
            
            # Save to JSON
            saved_file = self.save_tickets_to_json(tickets)
            
            if saved_file:
                print(f"\n{Fore.GREEN}📁 Data saved successfully!{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Next step: Run 'python3 ticket_analyzer.py {saved_file}' to analyze the data{Style.RESET_ALL}")
            
            # Log statistics
            logger.info("=== FETCH SUMMARY ===")
            logger.info(f"Total tickets fetched: {len(tickets)}")
            logger.info(f"JQL query used: {self.DEFAULT_JQL}")
            logger.info(f"Data saved to: {saved_file}")
        else:
            logger.warning("No tickets were fetched")
            print(f"{Fore.YELLOW}No tickets were fetched. Check your JQL query or connection.{Style.RESET_ALL}")

def main():
    """Main function"""
    try:
        fetcher = JiraTicketFetcher()
        fetcher.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 
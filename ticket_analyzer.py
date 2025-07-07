#!/usr/bin/env python3
"""
Ticket Analyzer with Local AI Processing
Analyzes Jira tickets using Ollama locally.
No data is sent to external AI services.
"""

import os
import sys
import json
import ollama
from datetime import datetime
from typing import List, Dict, Any
from tabulate import tabulate
from colorama import init, Fore, Style
from dotenv import load_dotenv

# Initialize colorama for colored output
init()

class TicketAnalyzer:
    def __init__(self):
        load_dotenv()
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2')
        self.ticket_data = None
        self.tickets = []
    
    def test_ollama_connection(self) -> bool:
        """Test connection to Ollama"""
        try:
            models = ollama.list()
            available_models = [m['name'] for m in models['models']]
            
            if self.ollama_model in available_models:
                print(f"{Fore.GREEN}✓ Ollama model '{self.ollama_model}' is available{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.YELLOW}! Model '{self.ollama_model}' not found. Available models: {', '.join(available_models)}{Style.RESET_ALL}")
                if available_models:
                    self.ollama_model = available_models[0]
                    print(f"{Fore.YELLOW}Using '{self.ollama_model}' instead{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}✗ No Ollama models available. Please install a model first.{Style.RESET_ALL}")
                    print("Run: ollama pull llama3.2")
                    return False
        except Exception as e:
            print(f"{Fore.RED}✗ Ollama connection error: {str(e)}{Style.RESET_ALL}")
            print("Make sure Ollama is running: ollama serve")
            return False
    
    def load_ticket_data(self, filename: str) -> bool:
        """Load ticket data from JSON file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.ticket_data = json.load(f)
                self.tickets = self.ticket_data.get('tickets', [])
            
            print(f"{Fore.GREEN}✓ Loaded {len(self.tickets)} tickets from {filename}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Data info:{Style.RESET_ALL}")
            print(f"  Fetched: {self.ticket_data.get('fetch_timestamp', 'Unknown')}")
            print(f"  JQL Query: {self.ticket_data.get('jql_query', 'Unknown')}")
            print(f"  Total tickets: {self.ticket_data.get('total_tickets', 0)}")
            return True
        except FileNotFoundError:
            print(f"{Fore.RED}✗ File not found: {filename}{Style.RESET_ALL}")
            return False
        except json.JSONDecodeError as e:
            print(f"{Fore.RED}✗ Invalid JSON in file: {str(e)}{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}✗ Error loading file: {str(e)}{Style.RESET_ALL}")
            return False
    
    def prepare_ticket_data_for_analysis(self) -> str:
        """Prepare ticket data for AI processing"""
        ticket_summaries = []
        
        for ticket in self.tickets:
            fields = ticket['fields']
            
            # Extract relevant information
            key = ticket['key']
            summary = fields.get('summary', '')
            description = fields.get('description', '')
            status = fields.get('status', {}).get('name', 'Unknown')
            priority = fields.get('priority', {}).get('name', 'Unknown')
            issue_type = fields.get('issuetype', {}).get('name', 'Unknown')
            
            assignee = fields.get('assignee')
            assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
            
            reporter = fields.get('reporter')
            reporter_name = reporter.get('displayName', 'Unknown') if reporter else 'Unknown'
            
            created = fields.get('created', '')[:10]  # Just the date part
            updated = fields.get('updated', '')[:10]  # Just the date part
            
            # Truncate description if too long
            if description and len(description) > 300:
                description = description[:300] + "..."
            
            # Extract comments if available
            comments = []
            comment_field = fields.get('comment', {})
            if comment_field and 'comments' in comment_field:
                for comment in comment_field['comments'][-3:]:  # Last 3 comments
                    author = comment.get('author', {}).get('displayName', 'Unknown')
                    body = comment.get('body', '')
                    if len(body) > 150:
                        body = body[:150] + "..."
                    comments.append(f"  {author}: {body}")
            
            comments_text = '\n'.join(comments) if comments else 'No comments'
            
            # Extract recent history if available
            history_items = []
            changelog = ticket.get('changelog', {})
            if changelog and 'histories' in changelog:
                for history in changelog['histories'][-2:]:  # Last 2 history entries
                    author = history.get('author', {}).get('displayName', 'Unknown')
                    for item in history.get('items', []):
                        field = item.get('field', '')
                        from_val = item.get('fromString', '')
                        to_val = item.get('toString', '')
                        history_items.append(f"  {author}: {field} changed from '{from_val}' to '{to_val}'")
            
            history_text = '\n'.join(history_items) if history_items else 'No recent changes'
            
            ticket_summary = f"""
Ticket: {key}
Title: {summary}
Type: {issue_type}
Status: {status}
Priority: {priority}
Assignee: {assignee_name}
Reporter: {reporter_name}
Created: {created}
Updated: {updated}
Description: {description or 'No description'}
Recent Comments:
{comments_text}
Recent History:
{history_text}
---
"""
            ticket_summaries.append(ticket_summary)
        
        return "\n".join(ticket_summaries)
    
    def analyze_with_ollama(self, ticket_data: str, analysis_type: str = "summary") -> str:
        """Analyze ticket data using Ollama locally"""
        prompts = {
            "summary": """
Please analyze these Jira tickets and provide:

1. **Executive Summary** (2-3 sentences about the overall state)
2. **Key Statistics** (count by status, priority, type)
3. **Main Themes** (what are the common issues/topics)
4. **Priority Issues** (highlight high-priority or urgent items)
5. **Recommendations** (actionable insights for the team/manager)

Keep the analysis concise and manager-friendly. Focus on actionable insights.

Ticket Data:
""",
            "detailed": """
You are a senior analyst reviewing 600 Level 2 tech support Jira tickets. Your goal is to extract operational and team performance insights. Provide specific, data-driven answers. Be concise, but insightful. Avoid generic statements.

Analyze the following:

1. 🔁 **Recurring Issues & Technical Trends**
   - Cluster similar tickets by keywords or symptoms (e.g. "timeout", "duplicate entry", "3DS failure")
   - Give counts per cluster and example ticket IDs
   - Identify what systems/modules cause the most trouble

2. 👤 **Most Valuable Personnel**
   - Who resolves the most tickets?
   - Who handles the most complex tickets? (longest descriptions, critical priority)
   - Who closes tickets fastest (median resolution time)?
   - Who gets stuck most often? (tickets blocked or not updated >7 days)

3. 🧱 **Bottlenecks & Risks**
   - Where are tickets getting stuck? (statuses, handoffs, specific assignees)
   - Are there neglected tickets (e.g., open for >14 days)?
   - Are high-priority tickets resolved faster than low-priority ones?

4. 🗓️ **Time-Based Trends**
   - Ticket volume by week/month
   - Resolution time trends: is it improving?
   - Peaks in ticket creation or slowdowns in resolution — identify and explain

5. 📈 **Process and Workflow Patterns**
   - Average number of status transitions per ticket
   - Any patterns in ticket reopenings?
   - Any assignee-specific patterns? (e.g. "Assignee X always gets API errors")

6. 🚨 **Actionable Recommendations**
   - Suggest team/process improvements
   - Propose which recurring issues should be fixed at the root
   - Identify where automation could reduce ticket load

Be specific. Use bullet points and tables where appropriate. Include counts, percentages, and ticket IDs. This analysis is for a support team manager who wants to improve efficiency, identify top performers, and reduce recurring problems.

Ticket Data:
""",
            "trends": """
Analyze these Jira tickets for detailed trends and actionable insights. Provide specific data points, numbers, and examples where possible:

## 1. **TEMPORAL ANALYSIS**
- **Ticket Volume by Time**: Count tickets created per day/week/month. Identify peak periods and quiet times.
- **Time-to-Resolution**: Calculate average time from creation to resolution for different ticket types and priorities.
- **Age Analysis**: Identify tickets that have been open for unusually long periods.

## 2. **WORKFLOW & STATUS ANALYSIS**
- **Status Distribution**: Current count of tickets in each status (To Do, In Progress, Pending, Blocked, Done, etc.)
- **Stuck Tickets Analysis**: 
  - List tickets in "Pending" status for >X days with specific ticket IDs
  - List tickets in "Blocked" status for >X days with specific ticket IDs
  - Identify which tickets haven't been updated recently
- **Status Transition Patterns**: How tickets typically flow through statuses

## 3. **WORKLOAD & ASSIGNEE ANALYSIS**
- **Tickets per Assignee**: Count and percentage breakdown by team member
- **Assignee Performance Patterns**: 
  - Who has the most open tickets?
  - Who resolves tickets fastest/slowest?
  - Which assignees have tickets stuck in specific statuses?
- **Workload Balance**: Identify overloaded vs underutilized team members

## 4. **PROBLEM PATTERN ANALYSIS**
- **Similar Issue Clustering**: Group tickets with very similar titles, descriptions, or error patterns
  - Example: "Payment processing errors" (count: X tickets)
  - Example: "API timeout issues" (count: X tickets)  
  - Example: "Database connection problems" (count: X tickets)
- **Recurring Keywords**: Most frequent words/phrases in ticket descriptions
- **Error Pattern Detection**: Common error codes, system names, or technical issues

## 5. **DEPENDENCY & CORRELATION ANALYSIS**
- **Assignee-Specific Patterns**: 
  - Does Assignee X always get certain types of tickets?
  - Which assignees have recurring similar problems?
  - Are some team members specialists in specific areas?
- **Subject-Matter Dependencies**: 
  - Which topics/systems generate the most tickets?
  - Are certain subjects always assigned to the same people?
  - What are the most problematic systems/features?

## 6. **PRIORITY & IMPACT ANALYSIS**
- **Priority Distribution**: Breakdown by High/Medium/Low priority
- **Priority vs Time-to-Resolution**: Do high-priority tickets actually get resolved faster?
- **Escalation Patterns**: Which types of tickets tend to get escalated?

## 7. **ACTIONABLE RECOMMENDATIONS**
Based on the patterns found, provide specific recommendations:
- Which processes need improvement?
- Where are the bottlenecks?
- What training might be needed?
- How to better distribute workload?
- Which recurring issues need permanent fixes?

**IMPORTANT**: For each insight, provide:
- Specific numbers and percentages
- Actual ticket IDs as examples where relevant
- Clear actionable recommendations
- Potential root causes for identified problems

Ticket Data:
"""
        }
        
        prompt = prompts.get(analysis_type, prompts["summary"]) + ticket_data
        
        try:
            print(f"{Fore.YELLOW}🤖 Analyzing tickets with {self.ollama_model}...{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}This may take a moment...{Style.RESET_ALL}")
            
            response = ollama.chat(
                model=self.ollama_model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }]
            )
            
            return response['message']['content']
        
        except Exception as e:
            print(f"{Fore.RED}✗ Error analyzing with Ollama: {str(e)}{Style.RESET_ALL}")
            return "Analysis failed. Please check Ollama connection."
    
    def display_ticket_table(self):
        """Display tickets in a nice table format"""
        if not self.tickets:
            print(f"{Fore.YELLOW}No tickets to display{Style.RESET_ALL}")
            return
        
        table_data = []
        for ticket in self.tickets:
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
    
    def save_analysis(self, analysis: str, analysis_type: str, filename: str = None):
        """Save analysis to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ticket_analysis_{analysis_type}_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Ticket Analysis ({analysis_type.title()}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Source data: {self.ticket_data.get('fetch_timestamp', 'Unknown')}\n")
                f.write(f"JQL Query: {self.ticket_data.get('jql_query', 'Unknown')}\n")
                f.write(f"Total tickets analyzed: {len(self.tickets)}\n")
                f.write(f"AI Model: {self.ollama_model}\n")
                f.write("\n" + "=" * 60 + "\n\n")
                f.write(analysis)
            
            print(f"{Fore.GREEN}✓ Analysis saved to {filename}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}✗ Failed to save analysis: {str(e)}{Style.RESET_ALL}")
    
    def quick_summary(self):
        """Quick summary analysis"""
        print(f"\n{Fore.YELLOW}Generating quick summary...{Style.RESET_ALL}")
        
        self.display_ticket_table()
        ticket_data = self.prepare_ticket_data_for_analysis()
        analysis = self.analyze_with_ollama(ticket_data, "summary")
        
        print(f"\n{Fore.CYAN}📊 Quick Summary:{Style.RESET_ALL}")
        print(analysis)
        
        save = input(f"\n{Fore.YELLOW}Save analysis to file? (y/n): {Style.RESET_ALL}").strip().lower()
        if save == 'y':
            self.save_analysis(analysis, "summary")
    
    def detailed_analysis(self):
        """Detailed analysis"""
        print(f"\n{Fore.YELLOW}Generating detailed analysis...{Style.RESET_ALL}")
        
        self.display_ticket_table()
        ticket_data = self.prepare_ticket_data_for_analysis()
        analysis = self.analyze_with_ollama(ticket_data, "detailed")
        
        print(f"\n{Fore.CYAN}📊 Detailed Analysis:{Style.RESET_ALL}")
        print(analysis)
        
        save = input(f"\n{Fore.YELLOW}Save analysis to file? (y/n): {Style.RESET_ALL}").strip().lower()
        if save == 'y':
            self.save_analysis(analysis, "detailed")
    
    def trend_analysis(self):
        """Trend analysis"""
        print(f"\n{Fore.YELLOW}Generating trend analysis...{Style.RESET_ALL}")
        
        ticket_data = self.prepare_ticket_data_for_analysis()
        analysis = self.analyze_with_ollama(ticket_data, "trends")
        
        print(f"\n{Fore.CYAN}📈 Trend Analysis:{Style.RESET_ALL}")
        print(analysis)
        
        save = input(f"\n{Fore.YELLOW}Save analysis to file? (y/n): {Style.RESET_ALL}").strip().lower()
        if save == 'y':
            self.save_analysis(analysis, "trends")
    
    def run_interactive(self):
        """Run interactive analysis mode"""
        print(f"{Fore.CYAN}🤖 Ticket Analyzer with Local AI{Style.RESET_ALL}")
        print("=" * 50)
        
        # Test Ollama connection
        if not self.test_ollama_connection():
            return
        
        while True:
            print(f"\n{Fore.CYAN}Analysis Options:{Style.RESET_ALL}")
            print("1. Quick Summary")
            print("2. Detailed Analysis") 
            print("3. Trend Analysis")
            print("4. Show Ticket Table")
            print("5. Exit")
            
            choice = input(f"\n{Fore.YELLOW}Choose an option (1-5): {Style.RESET_ALL}").strip()
            
            if choice == "1":
                self.quick_summary()
            elif choice == "2":
                self.detailed_analysis()
            elif choice == "3":
                self.trend_analysis()
            elif choice == "4":
                self.display_ticket_table()
            elif choice == "5":
                print(f"{Fore.GREEN}Goodbye!{Style.RESET_ALL}")
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")
    
    def run_single_analysis(self, analysis_type: str):
        """Run a single analysis and exit"""
        if not self.test_ollama_connection():
            return
        
        print(f"\n{Fore.CYAN}Running {analysis_type} analysis...{Style.RESET_ALL}")
        
        if analysis_type == "summary":
            self.quick_summary()
        elif analysis_type == "detailed":
            self.detailed_analysis()
        elif analysis_type == "trends":
            self.trend_analysis()
        else:
            print(f"{Fore.RED}Unknown analysis type: {analysis_type}{Style.RESET_ALL}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print(f"{Fore.RED}Usage: python3 ticket_analyzer.py <json_file> [analysis_type]{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Example: python3 ticket_analyzer.py jira_tickets_20240624_163000.json{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Analysis types: summary, detailed, trends (optional - if not specified, runs interactive mode){Style.RESET_ALL}")
        sys.exit(1)
    
    json_file = sys.argv[1]
    analysis_type = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        analyzer = TicketAnalyzer()
        
        # Load ticket data
        if not analyzer.load_ticket_data(json_file):
            sys.exit(1)
        
        # Run analysis
        if analysis_type:
            analyzer.run_single_analysis(analysis_type)
        else:
            analyzer.run_interactive()
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Convert IsDB tenders JSON to comprehensive CSV with all text data
"""

import json
import csv

# Read the JSON file
with open('/workspace/isdb_tenders_full.json', 'r', encoding='utf-8') as f:
    tenders = json.load(f)

# Define all fields for CSV
fieldnames = [
    'title',
    'status', 
    'tender_type',
    'country',
    'close_date',
    'url',
    'node_id',
    'full_title',
    'notice_type',
    'issue_date',
    'project_code',
    'project_title',
    'contact_email',
    'description',
    'attachments',
    'all_emails',
    'contract_award_company',
    'contract_award_country',
    'contract_award_address'
]

# Process and flatten data
cleaned_data = []

for tender in tenders:
    row = {
        'title': tender.get('title', ''),
        'status': tender.get('status', ''),
        'tender_type': tender.get('tender_type', ''),
        'country': tender.get('country', ''),
        'close_date': tender.get('close_date', ''),
        'url': tender.get('url', ''),
        'node_id': tender.get('node_id', ''),
    }
    
    # Extract details
    details = tender.get('details', {})
    
    row['full_title'] = details.get('full_title', '')
    
    # Clean notice type (remove prefix)
    notice_type = details.get('notice_type', '')
    if notice_type.startswith('Notice Type'):
        notice_type = notice_type.replace('Notice Type', '').strip()
    row['notice_type'] = notice_type
    
    # Clean issue date
    issue_date = details.get('issue_date', '')
    if issue_date.startswith('Issue Date'):
        issue_date = issue_date.replace('Issue Date', '').strip()
    row['issue_date'] = issue_date
    
    # Clean project code
    project_code = details.get('project_code', '')
    if project_code.startswith('Project code'):
        project_code = project_code.replace('Project code', '').strip()
    row['project_code'] = project_code
    
    # Clean project title
    project_title = details.get('project_title', '')
    if project_title.startswith('Project title'):
        project_title = project_title.replace('Project title', '').strip()
    row['project_title'] = project_title
    
    # Clean email
    email = details.get('email', '')
    if email.startswith('Email'):
        email = email.replace('Email', '').strip()
    row['contact_email'] = email
    
    # Description (clean text)
    row['description'] = details.get('description', '')
    
    # Attachments as list
    attachments = details.get('attachments', [])
    if attachments:
        att_list = [f"{a.get('name', '')} ({a.get('url', '')})" for a in attachments]
        row['attachments'] = ' | '.join(att_list)
    else:
        row['attachments'] = ''
    
    # All emails found
    emails = details.get('emails_found', [])
    row['all_emails'] = ', '.join(emails) if emails else ''
    
    # Contract award info
    contract_name = details.get('contract_award_name', '')
    if contract_name.startswith('Contract Award Company Name'):
        contract_name = contract_name.replace('Contract Award Company Name', '').strip()
    row['contract_award_company'] = contract_name
    
    contract_country = details.get('contract_award_country', '')
    if contract_country.startswith('Contract Award Company Country'):
        contract_country = contract_country.replace('Contract Award Company Country', '').strip()
    row['contract_award_country'] = contract_country
    
    contract_address = details.get('contract_award_address', '')
    if contract_address.startswith('Contract Award Company Address'):
        contract_address = contract_address.replace('Contract Award Company Address', '').strip()
    row['contract_award_address'] = contract_address
    
    cleaned_data.append(row)

# Write to CSV
output_file = '/workspace/isdb_tenders_complete.csv'
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cleaned_data)

print(f"Created: {output_file}")
print(f"Total records: {len(cleaned_data)}")
print(f"Columns: {len(fieldnames)}")
print(f"\nColumns included:")
for col in fieldnames:
    print(f"  - {col}")

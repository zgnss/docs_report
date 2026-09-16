import boto3
from os import getenv, uname
from dotenv import load_dotenv
from argparse import ArgumentParser
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from smtplib import SMTP
from botocore.client import Config

def parse_args():
    parser = ArgumentParser(description='Shows cloud storage usage data, and sends out via email if desired.')
    parser.add_argument('buckets', help='A list of one or more buckets to report usage for', nargs='+')
    parser.add_argument('-a', '--return-address', type=str, default='reporting@nss-corp.com', help='The return address to specify in email headers')
    parser.add_argument('-e', '--email', action='store_true', help='Send data via email')
    parser.add_argument('-n', '--report-name', type=str, default='Default NSS Cloud', help='The name for the report')
    parser.add_argument('-p', '--print', action='store_true', help='Print data to stdout')
    parser.add_argument('-r', '--recipients', type=str, default='helpdesk@nss-corp.com',  help='Comma-separated email email recipient list')
    parser.add_argument('-v', '--verbose', action='store_true',  help='Verbose output for debugging')
    args = parser.parse_args()
    return args

def send_email(subject, content, email_to, email_from='reporting@nss-corp.com', email_from_name='NSS Reporting'):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = formataddr((email_from_name, email_from))
    msg['To'] = email_to
    msg.set_content(content)

    try:
        with SMTP('localhost', 25) as server:
            server.send_message(msg)
    except Exception as e:
        print(f'Failed to send email: {e}')

if __name__ == '__main__':
    # Load .env
    load_dotenv()

    # Parse arguments
    args = parse_args()

    # Check that we're either printing or emailing the ouput
    if not args.print and not args.email:
        print('No action specified (-e|-p). Exiting.')
        exit(0)

    # Connect to DigitalOcean Spaces, using config from .env file
    session = boto3.session.Session()
    s3_client = session.client(
        's3',
        region_name=getenv('SPACES_REGION'),
    endpoint_url=getenv('SPACES_ENDPOINT'),
    aws_access_key_id=getenv('SPACES_KEY'),
    aws_secret_access_key=getenv('SPACES_SECRET'),
    config=Config(
            s3={'addressing_style': 'virtual'},
        )
    )
    
    # Calculate the month name of last month and generate a month/year string, e.g. August 2026
    first_day = date.today().replace(day=1)
    last_day = first_day - timedelta(days=1)
    date_str = last_day.strftime('%B %Y')

    # Initialize total usage size as 0
    total_size_bytes = 0
    # Instantiate a paginator to read through multiple pages of objects
    paginator = s3_client.get_paginator('list_objects_v2')
    # Build the string containing the data
    usage_data = f'{args.report_name} storage usage for {date_str}:\r\n\r\n'
    usage_data += f'Breakdown\r\n\r\n'
    # Loop through CLI position args
    for bucket in args.buckets:
        # Set current bucket size counter to 0
        bucket_size_bytes = 0
        # Loop contents with the paginator
        for page in paginator.paginate(Bucket=bucket):
            if 'Contents' in page:
                for obj in page['Contents']:
                    obj_size = obj['Size']
                    # Pull the 'Size' value of the current file and add to the bucket size counter
                    bucket_size_bytes += obj_size
                    # Add the current object size to the total counter for all buckets
                    total_size_bytes += obj_size
        # Convert from bytes to GiB
        bucket_size_gb = bucket_size_bytes / (1024 ** 3)
        # Add the bucket size to the string
        usage_data += f'{bucket}: {bucket_size_gb:.2f} GiB\r\n'
    total_size_gb = total_size_bytes / (1024 ** 3)
    # Extra new line before text, for formatting
    usage_data += f'\r\nTotal usage: {total_size_gb:.2f} GiB\r\n\r\n'
    usage_data += f'Report generated on {uname().nodename}'
    
    if args.print:
        print(usage_data)

    if args.email:
        # Split recipient list out, clean address whitespace, end send emails
        if args.recipients:
            recipients = args.recipients.split(',')
        email_subject = f'{args.report_name} Storage Usage For {date_str}'
        for recipient in recipients:
            clean_addr = recipient.strip()
            if args.verbose:
                print(f'Emailing {args.report_name} storage usage report to {clean_addr}...')
            send_email(email_subject, usage_data, recipient, email_from=args.return_address)

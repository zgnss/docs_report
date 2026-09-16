#!/usr/bin/bash

# Activate the venv with the required libraries
. /usr/scripts/.venv/bin/activate

# Call the script to send the email
python /usr/scripts/docs_report.py -n 'Example' -er 'your@email.tld' bucket1 bucket1-cold

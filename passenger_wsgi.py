import sys
import os

# 1. FORCE THE PATH
# This tells Python to look in your specific folder, ignoring the 
# confusion caused by the dots in 'erp.edusaint.in'.
project_home = '/home/lxyscuzf/erp.edusaint.in'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 2. IMPORT THE APP
# We import the 'app' variable from your 'main.py' file and 
# rename it to 'application' so the server knows what to run.
from main import app as application
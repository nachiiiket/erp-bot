import os

# Backward-compatible names for older imports. Store real values in environment
# variables, not in this module.
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
MONGO_ROOT_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
OTP_SECRET_KEY = os.environ.get('OTP_SECRET_KEY', '')
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
KEY = os.environ.get('FERNET_ENCRYPTION_SECRET_KEY', '')

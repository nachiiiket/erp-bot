import os


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bytes(name: str, default: bytes = b'') -> bytes:
    return os.environ.get(name, '').encode() or default


HOST = os.environ.get('APP_HOST', 'http://localhost:8000')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', '')
JWT_ALGORITHM = 'HS256'
OTP_SECRET_KEY = os.environ.get('OTP_SECRET_KEY', '')
OTP_VALID_TIME = _env_int('OTP_VALID_TIME', 180) # Seconds
PASSWORD_EXPIRY_TIME = _env_int('PASSWORD_EXPIRY_TIME', 180) # Days
PASSWORD_LOCK_EXPIRY = _env_int('PASSWORD_LOCK_EXPIRY', 3) # Minutes
MAX_ATTEMPTS = _env_int('MAX_ATTEMPTS', 3)
TOKEN_EXPIRY_DAYS = _env_int('TOKEN_EXPIRY_DAYS', 7)
PHOTO_SIZE_KB = _env_int('PHOTO_SIZE_KB', 700) # KB
OTP_TIMEOUT_MINUTES = _env_int('OTP_TIMEOUT_MINUTES', 3) # Minutes
SECRET_KEY = _env_bytes('APP_ENCRYPTION_KEY')
IV = _env_bytes('APP_ENCRYPTION_IV')

UUID_PATTERN = r"\{(\d{4}-\d{4}-\d{8})\}"

## Mongo Default Config
MONGO_CONFIG = {
    'host': os.environ.get('MONGO_HOST', 'localhost'),
    'port': os.environ.get('MONGO_PORT', '27017'),
    'database': os.environ.get('MONGO_DATABASE', ''),
    'user': os.environ.get('MONGO_USER', ''),
    'password': os.environ.get('MONGO_PASSWORD', ''),
    'collection': os.environ.get('MONGO_COLLECTION', ''),
    'chat_collection': os.environ.get('MONGO_CHAT_COLLECTION', ''),
    'cpl_data_collection': os.environ.get('MONGO_CPL_DATA_COLLECTION', ''),
}

  
  
# Email Config
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp-mail.outlook.com')
EMAIL_PORT = _env_int('EMAIL_PORT', 587)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() in {'1', 'true', 'yes', 'on'}
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# Middleware Config
BRUTE_FORCE_TIMEOUT = 60
BRUTE_FORCE_THRESHHOLD = 30
LOGIN_URL = '/login/'

# DDoS Middleware Config
TIME_WINDOW = 60
REQUEST_LIMIT = 1000

# Use setting timezone
TIMEZONE = 'Asia/Kolkata'


# s3 bucket aws configuration's
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')
AWS_PRESIGNED_EXPIRATION = _env_int('AWS_PRESIGNED_EXPIRATION', 3600)

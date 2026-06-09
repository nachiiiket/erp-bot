import re
import json
import requests
import base64
import phonenumbers
import boto3
import jwt
from PIL import Image
from io import BytesIO
from django.http import JsonResponse
from utilities import status, constants
from datetime import datetime, timedelta
from django.utils import timezone
from utilities.config import PASSWORD_EXPIRY_TIME
from phonenumber_field.modelfields import PhoneNumber
from phonenumbers.phonenumberutil import region_code_for_country_code
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from utilities import config, constants
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from django.utils.timezone import make_aware, now
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature
from channels.layers import get_channel_layer
from botocore.exceptions import ClientError


def datetime_to_epoch(dt):
    return int(dt.strftime('%s')) * 1000

def epoch_to_datetime(epoach):
    return datetime.fromtimestamp(epoach/1000)

def epoch_to_utcdate(epoach):
    return datetime.utcfromtimestamp(epoach/1000)

def prepare_response(content={}, message='', status=status.HTTP_200_OK, paginator=None, total_records=0):
    resp = {
        "content": content,
        "message": message,
        "status": status
    }
    if paginator:
        resp['pagination'] = {
            'has_previous': paginator.has_previous(),
            'has_next': paginator.has_next(),
            'previous_page_number': paginator.previous_page_number() if paginator.has_previous() else None,
            'next_page_number': paginator.next_page_number() if paginator.has_next() else None,
            'page_number': paginator.number,
            'total_records': total_records
        }
    return JsonResponse(resp, status=status)

def validate_mobile(value):
    rule = re.compile(r'^\d{9}$')
    if rule.search(value):
        return True
    else:
        return False

def validate_email(email):
    if not re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email):
        return True
    return False    

def validate_password(password):
    if len(password) < 8 or \
        not re.search('[a-z]', password) or \
        not re.search('[A-Z]', password) or \
        not re.search('[0-9]', password) or \
        not re.search("[!@#$%^&*(),.?':{}|<>]", password):
        return True
    return False
    
def is_password_expire(user_profile):
    last_change_date = user_profile.password_change_timestamp
    if last_change_date is not None:
        expiration_date = last_change_date + timedelta(days=PASSWORD_EXPIRY_TIME) 
        if timezone.now() > expiration_date:
            return True  
    return False  

def resize_image(photo_base64, target_size_kb):
    decoded_photo = base64.b64decode(photo_base64)
    img = Image.open(BytesIO(decoded_photo))
    img = img.convert('RGB')
    target_size = target_size_kb * 1024

    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    original_size = buffer.tell()

    if original_size > target_size:
        quality = int(95 * target_size / original_size)
        buffer = BytesIO()  
        img.save(buffer, format='JPEG', quality=quality)
    resized_photo = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
    return resized_photo

def validate_phone_number(value):
    regions = ['IN', 'US'] 
    try:
        phone_number = PhoneNumber.from_string(value)
        parsed_region = region_code_for_country_code(phone_number.country_code)
        if parsed_region not in regions:
            return {'message':constants.INVALID_CONTACT_NUMBER_FORMAT } 
        if not phonenumbers.is_valid_number(phone_number):
            return {'message':constants.INVALID_CONTACT_NUMBER}
        return True
    except:
        return {'message': constants.INVALID_CONTACT_NUMBER}
    
def send_email(subject, recipient_list, message="", template=None, file_path=None, bcc_emails=None, cc_emails=None):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=settings.EMAIL_HOST_USER,
        to=recipient_list,
        bcc=bcc_emails,
        cc=cc_emails,
    )
    if file_path:
        msg.attach_file(file_path)
          
    if template:
        message = render_to_string(template.get('path'), template.get('context'))
        msg.attach_alternative(message, "text/html")   
    msg.send()

      
def flatten_json(y):
    out = {}
    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '.')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '.')
                i += 1
        else:
            out[name[:-1]] = x
    flatten(y)
    return out


## Updated nested dict with new one
def update_nested_dict(original_dict, new_dict):
    for key, value in new_dict.items():
        if key in original_dict and isinstance(original_dict[key], dict) and isinstance(value, dict):
            # If both values are dictionaries, recursively update
            update_nested_dict(original_dict[key], value)
        else:
            # Otherwise, update the value
            original_dict[key] = value
            

def mask_string(input_string, start, end):
    masked_part = '*' * (end - start)
    masked_string = input_string[:start] + masked_part + input_string[end:]
    return masked_string


def create_periodic_task(task, report):
    schedule = None
    print("=================>", report.timeframes.all())

    # ---------- Report crontab Schedule ----------
    for timeframe in report.timeframes.all():

        if report.schedule_type == constants.DAILY:
            name = '{%s}-{%s}-{%s}' % (report.name, report.id, timeframe.name)

        elif report.schedule_type == constants.MONTHLY:
            name = '{%s}-{%s}-{%s}-{%s}' % (report.name, "monthly", report.id, timeframe.name)

        schedule, _ = CrontabSchedule.objects.update_or_create(
            minute='%s' % timeframe.end_time.minute,
            hour='%s' % timeframe.end_time.hour,
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            timezone=config.TIMEZONE
        )

        PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                'crontab': schedule,
                'task': task,
                'kwargs': json.dumps({
                    'report_id': report.id,
                    'timeframe_id': timeframe.id
                }),
            }
        )

    return schedule

def send_sms(api_key, sender_id, phone_number, message, template=None):
    url = "https://www.smsgatewayhub.com/api/mt/SendSMS"
    data = {
        'api_key': api_key,
        'sender_id': sender_id,
        'phone_number': phone_number,
        'message': message,
        'template': template

    }
    print(data)

    response = requests.post(url, data=data)
    return prepare_response(
        content=response,
        status=status.HTTP_200_OK
    )

def client_ip_address(request):
    ip_address = request.META.get("HTTP_X_FORWARDED_FOR")
    if ip_address:
        ip_address = ip_address.split(',')[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR")
    return ip_address


def validate_license(company):
    from core_service.models import LicenseKey
    try:
        license = LicenseKey.objects.get(company=company, is_active=True)

        # Decode payload and signature from base64
        payload_bytes = base64.b64decode(license.payload)
        signature = base64.b64decode(license.signature)

        # Load public key from stored PEM string
        public_key = serialization.load_pem_public_key(license.public_key.encode())

        # Verify the signature
        public_key.verify(
            signature,
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Parse payload JSON
        payload = json.loads(payload_bytes)
        # ---------- Check valid company licence ----------
        payload_company_id = payload.get("company_id")
        if int(payload_company_id) != int(company.id):
            return False, constants.COMPANY_ID_MISMATCH
        
        expires_at_raw = payload.get("expires_at")
        if not expires_at_raw:
            return False, constants.MISSING_EXPIRATION_DATE

        expires_at = make_aware(datetime.fromisoformat(expires_at_raw))
        if expires_at < now():
            return False, constants.LICENSE_EXPIRED

        return True, payload

    except LicenseKey.DoesNotExist:
        return False, constants.LICENSE_NOT_FOUND
    except InvalidSignature:
        return False, constants.INVALID_LICENSE_SIGNATURE
    except Exception as e:
        return False, constants.LICENSE_VERIFICATION_FAILED
    


def parse_log_entry(log):
    """Parse a log entry and return structured data."""
    parts = log.split(' - ')
    
    if len(parts) < 5:
        raise ValueError("Log entry format is incorrect.")
    date_time_str = parts[0].strip()
    try:
        date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S,%f')
        
        estamptime = int(date_time_obj.timestamp() * 1000) 
    except ValueError:
        raise ValueError("Date format is incorrect.")
    message = ' - '.join(parts[5:]).strip()  
    message = message.replace('None', '').strip()
    
    return {
        'type': constants.SERVER_LOGS,
        'timestamp': estamptime,  
        'description': message
    }


async def send_logger_data(data):
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "logs_group",  
        {
            "type": "send_log_notification", 
            "log": json.dumps(data)
        }
    )


def base64_to_file(base64_data, output_path):
    decoded_data = base64.b64decode(base64_data)
    # Write the decoded data to the output file
    with open(output_path, "wb") as f:
        f.write(decoded_data)

def upload_file_to_s3(file_path, bucket, object_name=None):
    # Upload a file to an S3 bucket

    if not object_name:
        object_name = file_path
    object_name = object_name.replace("%20", " ")

    # Upload the file
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=config.AWS_ACCESS_KEY,
        aws_secret_access_key=config.AWS_SECRET_KEY,
        region_name=config.AWS_REGION,
    )
    try:
        response = s3_client.upload_file(file_path, bucket, object_name)
    except ClientError as e:
        return False
    return True


def read_file(bucket_name, object_name):
    object_name = object_name.replace("%20", " ")
    s3_client = boto3.resource(
        "s3",
        aws_access_key_id=config.AWS_ACCESS_KEY,
        aws_secret_access_key=config.AWS_SECRET_KEY,
        region_name=config.AWS_REGION,
    )
    obj = s3_client.Object(bucket_name, object_name)
    body = obj.get()["Body"].read()
    return body



class MicrosoftService:
    MICROSOFT_GRAPH_API_URL = "https://graph.microsoft.com/v1.0/me"

    @staticmethod
    def validate_token(token):
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(MicrosoftService.MICROSOFT_GRAPH_API_URL, headers=headers)
        print("response= = = = =>",response)

        if response.status_code != 200:
            return False
        return response.json()
    

    @staticmethod
    def get_tenant_id(token):
        """
        Retrieves tenant id claim from token
        """
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        tenant_id = decoded_token.get("tid")
        return tenant_id
    
    
def get_duration_string(start_time, end_time):
    if not start_time or not end_time:
        return None

    delta = end_time - start_time  # timedelta

    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} days")
    if hours:
        parts.append(f"{hours} hours")
    if minutes:
        parts.append(f"{minutes} minutes")

    return " ".join(parts) if parts else "0 minutes"


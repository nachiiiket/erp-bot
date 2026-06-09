import json
from utilities.helper_functions import prepare_response,is_password_expire, validate_license
from utilities.jwt_token import decode_jwt_token, get_jwt_token
from utilities import status, constants
from django.contrib.auth.models import User
from public_api.models import ApiAccess
from core_service.models import UserProfile, ApiPermissions, RolePermission, Role
from django.contrib.auth.models import Group
from django.core.cache import caches
from django.conf import settings
from hashlib import md5
from django.utils.cache import patch_cache_control
from functools import wraps
from subscription.models import Plan
from django.apps import apps


MODEL_MAP = {
    model.__name__.lower(): model
    for app in apps.get_app_configs()
    for model in app.get_models()
}
    

def check_api_permissions(request, function, *args, **kwargs):
    user_profile = UserProfile.objects.get(user=request.user)
    role = user_profile.role
    if not role:
        return prepare_response(
            message=constants.USER_NOT_BELONG_TO_ANY_ROLE,
            status=status.HTTP_404_NOT_FOUND
        )
    
    # -------- Allow admin full access --------
    if "ADMIN" in role.name.upper():
        return function(request, *args, **kwargs)
    
    # -------- Allow media url's --------
    if request.path.startswith("/media/"):
        return function(request, *args, **kwargs)
    
    api_permissions = ApiPermissions.objects.filter(path=request.path, request_method=request.method)
    if not api_permissions.exists():
        return prepare_response(
            message=constants.PERMISSION_DENIED_SUCCESS,
            status=status.HTTP_400_BAD_REQUEST
        )
    
    api_permission = api_permissions.first()    
    
    if api_permission.permission.key == constants.CORE_SERVICE:
        return function(request, *args, **kwargs)
    
    user_permissions = RolePermission.objects.filter(role=role, permission=api_permission.permission)
    if not user_permissions.exists():
        return prepare_response(
            message=constants.PERMISSION_DOES_NOT_EXIST,
            status=status.HTTP_404_NOT_FOUND
        )
    
    user_permission = user_permissions.first()

    # -------- Check permission type against user role permissions --------
    if api_permission.permission_type == constants.VIEW_ONLY and user_permission.view_only:
        return function(request, *args, **kwargs)
    elif api_permission.permission_type == constants.MODIFIED and user_permission.modified:
        return function(request, *args, **kwargs)
    elif api_permission.permission_type == constants.ADD and user_permission.add:
        return function(request, *args, **kwargs)
    elif api_permission.permission_type == constants.DELETE and user_permission.delete:
        return function(request, *args, **kwargs)
    else:
       return prepare_response(
            message=constants.PERMISSION_DENIED_SUCCESS,
            status=status.HTTP_400_BAD_REQUEST
        )
       

def is_request_authenticated(function):
    def wrap(request, *args, **kwargs):
        token = request.headers.get('Authorization')
        api_key = request.headers.get('api-key') 
        secret_key = request.headers.get('secret-key')

        if api_key and secret_key:
            try:
                api_access = ApiAccess.objects.get(api_key=api_key, secret_key=secret_key)
                if not api_access.apis.filter(path=request.path).exists():
                    return prepare_response(
                        message=constants.UNAUTHORIZED_ENDPOINT,
                        status=status.HTTP_403_FORBIDDEN
                    )
                request.user = api_access.user_profile.user

                # Validate license for company from api_access
                company = api_access.user_profile.company
                valid, error = validate_license(company)
                if not valid:
                    return prepare_response(
                        message=error,
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                return function(request, *args, **kwargs)
            except ApiAccess.DoesNotExist:
                return prepare_response(
                    message=constants.INVALID_KEYS,
                    status=status.HTTP_401_UNAUTHORIZED
                )
        elif token:
            token = get_jwt_token(token) 
            if not token: 
                return prepare_response(
                        message=constants.INVALID_LOGIN_DETAILS, 
                        status=status.HTTP_401_UNAUTHORIZED
                    )   
            decoded = decode_jwt_token(token)
            if 'error' in decoded:
                return prepare_response(
                    message=decoded.get('error'), 
                    status=status.HTTP_401_UNAUTHORIZED
                ) 
            user_id = decoded.get('user_id')
            try:
                user_profile = UserProfile.objects.get(id=user_id, is_active=True)
                request.user = user_profile.user

                if is_password_expire(user_profile):
                    return prepare_response(
                        message=constants.PASSWORD_EXPIRED,
                        status=status.HTTP_401_UNAUTHORIZED
                    )

                # Validate license for user's company
                company = user_profile.company
                valid, error = validate_license(company)
                if not valid:
                    return prepare_response(
                        message=error,
                        status=status.HTTP_403_FORBIDDEN
                    )

                return check_api_permissions(request, function, *args, **kwargs)
            except UserProfile.DoesNotExist:
                return prepare_response(
                    message=constants.USER_NOT_ONBOARDED, 
                    status=status.HTTP_404_NOT_FOUND 
                )
        else:
            return prepare_response(
                message=constants.INVALID_LOGIN_DETAILS,
                status=status.HTTP_401_UNAUTHORIZED
            )
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


def is_admin_request_authenticated(function):
    def wrap(request, *args, **kwargs):
        token = request.headers.get('Authorization')
        if token:
            token = get_jwt_token(token) 
        if not token:
            return prepare_response(
                message=constants.INVALID_LOGIN_DETAILS,
                status=status.HTTP_401_UNAUTHORIZED
            )
        decoded = decode_jwt_token(token)
        if "error" in decoded:
            return prepare_response(
                message=decoded.get('error'), 
                status=status.HTTP_401_UNAUTHORIZED
            )
        user_id = decoded.get('user_id')
        try:
            user_profile = UserProfile.objects.get(id=user_id)
            request.user = user_profile.user
            if is_password_expire(user_profile):
                return prepare_response(
                    content={},
                    message=constants.PASSWORD_EXPIRED,
                    status=status.HTTP_401_UNAUTHORIZED
                ) 
            optiex_admin_role = Role.objects.get(name='OPTIEX-ADMIN')
            if user_profile.role == optiex_admin_role:
                return function(request, *args, **kwargs)
            else:
                return prepare_response(
                    message=constants.INVALID_LOGIN_DETAILS, 
                    status=status.HTTP_401_UNAUTHORIZED 
                )
        except User.DoesNotExist:
            return prepare_response(
                message=constants.USER_NOT_ONBOARDED, 
                status=status.HTTP_404_NOT_FOUND 
            )
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap



def cache_page_by_user(timeout):
    """
    Cache responses uniquely per user, query params, and request body.
    Prevents returning old data for dynamic requests.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                user_key = f"user_{request.user.id}"
            else:
                user_key = "anonymous"

            query_string = request.META.get("QUERY_STRING", "").strip()

            try:
                if request.body:
                    body_data = json.dumps(json.loads(request.body.decode('utf-8')), sort_keys=True)
                else:
                    body_data = ""
            except Exception:
                body_data = request.body.decode('utf-8', errors='ignore')

            raw_key = f"{view_func.__module__}.{view_func.__name__}.{user_key}.{query_string}.{body_data}"
            cache_key = md5(raw_key.encode("utf-8")).hexdigest()

            cache = caches[settings.CACHE_MIDDLEWARE_ALIAS]

            response = cache.get(cache_key)
            if response:
                patch_cache_control(response, private=True)
                return response

            response = view_func(request, *args, **kwargs)
            cache.set(cache_key, response, timeout)
            patch_cache_control(response, private=True)
            return response

        return _wrapped_view
    return decorator


def check_subscription_plan(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        company = UserProfile.objects.get(user=request.user).company

        api_permission = ApiPermissions.objects.filter(path=request.path, request_method=request.method).first()
        permission_key = api_permission.permission.key

        plan = Plan.objects.filter(subscription__companysubscription__company=company,features__name__icontains=permission_key.replace("_", " ")).first()
        if not plan:
            return prepare_response(message=constants.PLAN_NOT_AVAILABLE, status=status.HTTP_200_OK)

        value = (plan.data or {}).get("value")

        if isinstance(value, str):
            if value.upper() == "UNLIMITED":
                return view_func(request, *args, **kwargs)
            if value.upper() == "FALSE":
                return prepare_response(message=constants.PLEASE_UPGRADE_YOUR_PLAN, status=status.HTTP_200_OK)
            
        if isinstance(value, int) and plan.model_name:
            model_class = MODEL_MAP.get(plan.model_name.lower())

            models = {"company": company}
            if permission_key == "USER":
                models = {"company": company}
            elif permission_key in ["REPORT", "QUICK_ANALYSIS"]:
                models = {"plant__company": company}

            count = model_class.objects.filter(**models).count()
            if count >= value:
                return prepare_response(
                    message=constants.PERMISSION_LIMIT_REACHED.format(permission_key.title()),
                    status=status.HTTP_200_OK
                )

        return view_func(request, *args, **kwargs)

    return _wrapped_view


# ---------- prepare cache per requests ----------
def cache_page_per_request(timeout):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):

            if request.user.is_authenticated:
                user_key = f"user_{request.user.id}" 
            else:
                "anonymous"

            body_hash = md5(request.body).hexdigest()
            cache_key = f"{view_func.__module__}.{view_func.__name__}.{user_key}.{body_hash}"
            cache_key = md5(cache_key.encode('utf-8')).hexdigest()

            cache = caches[settings.CACHE_MIDDLEWARE_ALIAS]
            response = cache.get(cache_key)
            if not response:
                response = view_func(request, *args, **kwargs)
                cache.set(cache_key, response, timeout)
            patch_cache_control(response, private=True)
            return response
        return _wrapped_view
    return decorator
[1mdiff --git a/backend/config/settings.py b/backend/config/settings.py[m
[1mindex 92ae301..85d5ffa 100644[m
[1m--- a/backend/config/settings.py[m
[1m+++ b/backend/config/settings.py[m
[36m@@ -10,24 +10,38 @@[m [mFor the full list of settings and their values, see[m
 https://docs.djangoproject.com/en/6.1/ref/settings/[m
 """[m
 [m
[31m-#from pathlib import Path[m
 [m
[31m-# Build paths inside the project like this: BASE_DIR / 'subdir'.[m
[31m-#BASE_DIR = Path(__file__).resolve().parent.parent[m
[32m+[m[32mimport os[m
 from pathlib import Path[m
[32m+[m[32mfrom dotenv import load_dotenv[m
 [m
[32m+[m[32m# Build paths inside the project[m
 BASE_DIR = Path(__file__).resolve().parent.parent[m
 [m
[32m+[m[32m# Load environment variables from backend/.env[m
[32m+[m[32mload_dotenv(BASE_DIR / ".env")[m
[32m+[m
[32m+[m
 # Quick-start development settings - unsuitable for production[m
 # See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/[m
 [m
[31m-# SECURITY WARNING: keep the secret key used in production secret![m
[31m-SECRET_KEY = 'django-insecure-e4g3s7gst-__slszzwxn^$+h7xnb2z)#y^58%v^=4f&ew=p4a4'[m
 [m
[31m-# SECURITY WARNING: don't run with debug turned on in production![m
[31m-DEBUG = True[m
[32m+[m[32mSECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")[m
[32m+[m[32mDEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"[m
 [m
[31m-ALLOWED_HOSTS = [][m
[32m+[m[32mALLOWED_HOSTS = [[m
[32m+[m[32m    host.strip()[m
[32m+[m[32m    for host in os.getenv([m
[32m+[m[32m        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"[m
[32m+[m[32m    ).split(",")[m
[32m+[m[32m    if host.strip()[m
[32m+[m[32m][m
[32m+[m
[32m+[m[32mCSRF_TRUSTED_ORIGINS = [[m
[32m+[m[32m    origin.strip()[m
[32m+[m[32m    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")[m
[32m+[m[32m    if origin.strip()[m
[32m+[m[32m][m
 [m
 [m
 # Application definition[m
[36m@@ -81,17 +95,24 @@[m [mWSGI_APPLICATION = 'config.wsgi.application'[m
 # https://docs.djangoproject.com/en/6.1/ref/settings/#databases[m
 [m
 [m
[32m+[m[32mBASE_DIR = Path(__file__).resolve().parent.parent[m
[32m+[m[32mload_dotenv(BASE_DIR / ".env")[m
[32m+[m
[32m+[m
 DATABASES = {[m
[31m-    'default': {[m
[31m-        'ENGINE': 'django.db.backends.mysql',[m
[31m-        'NAME': 'eduflow',[m
[31m-        'USER': 'root',[m
[31m-        'PASSWORD': '',[m
[31m-        'HOST': '127.0.0.1',[m
[31m-        'PORT': '3306',[m
[31m-        'OPTIONS': {[m
[31m-            'charset': 'utf8mb4',[m
[31m-            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",[m
[32m+[m[32m    "default": {[m
[32m+[m[32m        "ENGINE": "django.db.backends.mysql",[m
[32m+[m[32m        "NAME": os.getenv("DB_NAME"),[m
[32m+[m[32m        "USER": os.getenv("DB_USER"),[m
[32m+[m[32m        "PASSWORD": os.getenv("DB_PASSWORD"),[m
[32m+[m[32m        "HOST": os.getenv("DB_HOST"),[m
[32m+[m[32m        "PORT": os.getenv("DB_PORT"),[m
[32m+[m[32m        "OPTIONS": {[m
[32m+[m[32m            "charset": "utf8mb4",[m
[32m+[m[32m            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",[m
[32m+[m[32m            "ssl": {[m
[32m+[m[32m                "ca": os.getenv("DB_SSL_CA"),[m
[32m+[m[32m            },[m
         },[m
     }[m
 }[m

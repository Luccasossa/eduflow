import os

PASSWORD_RESET_TIMEOUT = 3600  # el enlace vence en 1 hora
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "EduFlow <no-reply@eduflow.local>")

if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # imprime el correo en la terminal
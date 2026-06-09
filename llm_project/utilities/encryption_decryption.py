import os

from cryptography.fernet import Fernet

ENCRYPTION_SECRET_KEY = os.environ.get('FERNET_ENCRYPTION_SECRET_KEY', '')


def _fernet() -> Fernet:
    if not ENCRYPTION_SECRET_KEY:
        raise ValueError('FERNET_ENCRYPTION_SECRET_KEY is required for encryption helpers.')
    return Fernet(ENCRYPTION_SECRET_KEY)


def encrypt(password: str) -> str:
    fernet = _fernet()
    return fernet.encrypt(password.encode()).decode()

if __name__ == "__main__":
    password = input("Enter password to encrypt: ")
    encrypted = encrypt(password)
    print("Encrypted password", encrypted)


def decrypt(encrypted_password: str) -> str:
    fernet = _fernet()
    return fernet.decrypt(encrypted_password.encode()).decode()

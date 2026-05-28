from cryptography.fernet import Fernet, InvalidToken


class TokenCipherConfigError(ValueError):
    pass


class TokenCipher:
    def __init__(self, key: str | None) -> None:
        if not key:
            raise TokenCipherConfigError("TOKEN_ENCRYPTION_KEY is required")
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise TokenCipherConfigError(
                "TOKEN_ENCRYPTION_KEY must be a valid Fernet key"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        try:
            return self._fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("encrypted token could not be decrypted") from exc

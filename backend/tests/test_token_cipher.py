import pytest

from app.services.security.tokens import TokenCipher, TokenCipherConfigError

TEST_KEY = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="


def test_token_cipher_encrypts_without_returning_plaintext() -> None:
    cipher = TokenCipher(TEST_KEY)

    encrypted = cipher.encrypt("refresh-token")

    assert encrypted != "refresh-token"
    assert cipher.decrypt(encrypted) == "refresh-token"


def test_token_cipher_rejects_missing_key() -> None:
    with pytest.raises(TokenCipherConfigError, match="TOKEN_ENCRYPTION_KEY is required"):
        TokenCipher(None)


def test_token_cipher_rejects_invalid_key() -> None:
    with pytest.raises(TokenCipherConfigError, match="valid Fernet key"):
        TokenCipher("not-a-fernet-key")

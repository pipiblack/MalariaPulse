import unittest

from malariapulse.auth import create_remember_token, validate_remember_token


class RememberTokenTests(unittest.TestCase):
    def test_valid_token_is_bound_to_user_and_expiry(self):
        token = create_remember_token("admin@example.test", "test-secret", now=1_000, lifetime_seconds=300)

        self.assertTrue(validate_remember_token(token, "admin@example.test", "test-secret", now=1_299))
        self.assertFalse(validate_remember_token(token, "other@example.test", "test-secret", now=1_299))
        self.assertFalse(validate_remember_token(token, "admin@example.test", "test-secret", now=1_300))

    def test_tampered_or_wrongly_signed_token_is_rejected(self):
        token = create_remember_token("admin@example.test", "test-secret", now=1_000)
        payload, signature = token.split(".", 1)

        self.assertFalse(validate_remember_token(f"{payload}.{signature[:-1]}x", "admin@example.test", "test-secret", now=1_001))
        self.assertFalse(validate_remember_token(token, "admin@example.test", "different-secret", now=1_001))
        self.assertFalse(validate_remember_token("not-a-token", "admin@example.test", "test-secret", now=1_001))


if __name__ == "__main__":
    unittest.main()

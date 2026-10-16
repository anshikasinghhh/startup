from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


class AccountsLoginTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Dummy credentials for testing
        self.dummy_username = "test_entrepreneur"
        self.dummy_email = "test_entrepreneur@example.com"
        self.dummy_password = "SecurePassword123!"

        # Create dummy user in test DB
        self.user = User.objects.create_user(
            username=self.dummy_username,
            email=self.dummy_email,
            password=self.dummy_password,
            first_name="Jane",
            last_name="Doe",
        )

        # Create a second user where username is an email address (like anshi09@gmail.com)
        self.email_username = "anshi09@gmail.com"
        self.email_password = "Anshi09Password!"
        self.email_user = User.objects.create_user(
            username=self.email_username,
            email=self.email_username,
            password=self.email_password,
            first_name="Anshi",
        )

        self.login_url = reverse("accounts:login")
        self.register_url = reverse("accounts:register")
        self.logout_url = reverse("accounts:logout")

    def test_login_page_renders_successfully(self):
        """GET request to login page returns status 200 and loads login template."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_successful_with_dummy_credentials(self):
        """POST with valid dummy username and password logs in and redirects to dashboard."""
        response = self.client.post(
            self.login_url,
            {"username": self.dummy_username, "password": self.dummy_password},
            follow=True,
        )
        # Check redirect to dashboard
        self.assertRedirects(response, reverse("dashboard:dashboard"))
        # Check user is authenticated in session
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)

    def test_login_successful_with_email_as_username(self):
        """POST with email as username (e.g. anshi09@gmail.com) authenticates correctly."""
        response = self.client.post(
            self.login_url,
            {"username": self.email_username, "password": self.email_password},
            follow=True,
        )
        self.assertRedirects(response, reverse("dashboard:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.email_user.id)

    def test_login_failed_with_wrong_password(self):
        """POST with incorrect password fails, stays on page, and displays error."""
        response = self.client.post(
            self.login_url,
            {"username": self.dummy_username, "password": "WrongPassword999!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertIsNotNone(response.context["error"])
        self.assertContains(response, "Invalid username or password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_failed_with_nonexistent_user(self):
        """POST with non-existent username fails and shows error."""
        response = self.client.post(
            self.login_url,
            {"username": "non_existent_user_999", "password": "anypassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertContains(response, "Invalid username or password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout(self):
        """Logging out terminates the session and redirects to home."""
        # Log in first
        self.client.login(username=self.dummy_username, password=self.dummy_password)
        self.assertIn("_auth_user_id", self.client.session)

        # Log out
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_register_flow_and_subsequent_login(self):
        """Tests full registration of a new dummy user and immediate login with those credentials."""
        new_dummy_username = "new_founder"
        new_dummy_email = "new_founder@example.com"
        new_dummy_password = "FounderPassword2025!"

        # Register
        reg_response = self.client.post(
            self.register_url,
            {
                "first_name": "New",
                "last_name": "Founder",
                "username": new_dummy_username,
                "email": new_dummy_email,
                "password": new_dummy_password,
            },
        )
        self.assertRedirects(reg_response, self.login_url)

        # Confirm user exists in DB
        self.assertTrue(User.objects.filter(username=new_dummy_username).exists())

        # Now login with the newly registered dummy user
        login_response = self.client.post(
            self.login_url,
            {"username": new_dummy_username, "password": new_dummy_password},
            follow=True,
        )
        self.assertRedirects(login_response, reverse("dashboard:dashboard"))
        new_user = User.objects.get(username=new_dummy_username)
        self.assertEqual(int(self.client.session["_auth_user_id"]), new_user.id)

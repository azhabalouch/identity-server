import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    use_in_migrations = True
    def create_user(self, email, password):
        user = self.model(email=self.normalize_email(email).lower())
        user.set_password(password)
        user.save(using=self._db)
        return user
class User(AbstractBaseUser):
    """Root account record. Profile data lives in personas, not here."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, 
editable=False)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128, db_column="password_hash")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = None  # not used: the API issues tokens, not sessions
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()
    class Meta:
        db_table = "users"
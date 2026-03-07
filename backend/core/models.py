import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.postgres.fields import ArrayField

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True, default='')
    profile_pic = models.URLField(blank=True, default='')
    last_active = models.DateTimeField(auto_now=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.name or self.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    skills_text = models.TextField(blank=True, default='')
    intent_text = models.TextField(blank=True, default='')
    skill_embedding = ArrayField(models.FloatField(), size=384, null=True, blank=True)
    intent_embedding = ArrayField(models.FloatField(), size=384, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
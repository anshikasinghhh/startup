from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.
DOMAIN_CHOICES = [
    ('TECH', 'Technology & Software'),
    ('HEALTH', 'Healthcare & Medical'),
    ('EDTECH', 'Education & EdTech'),
    ('FINTECH', 'Finance & FinTech'),
    ('ECOM', 'E-commerce & Retail'),
    ('FOOD', 'Food & Beverage'),
    ('LOGISTICS', 'Transportation & Logistics'),
    ('ENV', 'Sustainability & Environment'),
    ('MEDIA', 'Entertainment & Media'),
    ('OTHER', 'Other'),
]

class Validate_form(models.Model):
    
    created_at = models.DateTimeField(auto_now_add=True)  # ✅ keep only this line
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)


    startup_idea = models.TextField()
    business_domain = models.CharField(max_length=50, choices=DOMAIN_CHOICES)
    problem_statement = models.TextField()
    business_goal = models.TextField()
    monetization_strategy = models.TextField()
    social_impact = models.TextField()
    timeline = models.TextField()

    feasibility_score = models.CharField(max_length=50, null=True, blank=True)
    feasibility_comment = models.TextField(null=True, blank=True)
    feasibility_level = models.CharField(max_length=50, null=True, blank=True)
    swot_analysis = models.TextField(null=True, blank=True)
    risk_score = models.CharField(max_length=50, null=True, blank=True)
    risk_comment = models.TextField(null=True, blank=True)

    monetization_suggestion = models.TextField(null=True, blank=True)


class Testimonial(models.Model):
    name = models.CharField(max_length=100)
    feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

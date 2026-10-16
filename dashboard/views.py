from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.db.models import Avg
from django.contrib.auth.models import User
from xhtml2pdf import pisa
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

import json
import time
import requests
from google import genai

from .models import Validate_form, Testimonial
from .forms import TestimonialForm

# ====================== API CONFIG ======================
from django.conf import settings

# Use Gemini API
GEMINI_API_KEY = settings.GEMINI_API_KEY
client = genai.Client(api_key=GEMINI_API_KEY)

MAX_RETRIES = 3  # Number of retry attempts for rate-limited requests


# ====================== AI HELPER ======================
def generate_response(prompt):
    """
    Uses Google Gemini API to generate responses.
    Retries across supported models with exponential backoff on rate limit (429) errors.
    """
    models_to_try = ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-flash-latest']
    last_error = None

    for model_name in models_to_try:
        for attempt in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )

                text = getattr(response, 'text', None)
                if text:
                    return text.strip()
                return "⚠️ Error: AI response was empty."

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # Check if it's a rate limit or service unavailable error
                if "429" in str(e) or "resource has been exhausted" in error_str or "too many requests" in error_str:
                    wait_time = 2 * (2 ** attempt)
                    print(f"⏳ Rate limited on {model_name} (attempt {attempt + 1}/{MAX_RETRIES}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif "503" in str(e) or "unavailable" in error_str or "404" in str(e):
                    # Fallback to the next model immediately
                    print(f"Model {model_name} unavailable ({e}), trying next model...")
                    break
                else:
                    print(f"Gemini API Error with {model_name}: {e}")
                    break

    return f"⚠️ API Error: {str(last_error)}" if last_error else "⚠️ API Limit Reached. Please wait a minute and try again."


# ====================== PAGES & VIEWS ======================

def testimonials_view(request):
    testimonials = Testimonial.objects.all().order_by('-created_at')
    form = TestimonialForm()

    if request.method == 'POST':
        form = TestimonialForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard:testimonials')

    context = {'testimonials': testimonials, 'form': form}
    return render(request, 'dashboard/testimonials.html', context)


def guide(request):
    return render(request, "dashboard/guide1.html")


# ====================== REPORTS ======================
@login_required
def download_report(request):
    user = request.user
    submissions = Validate_form.objects.filter(user=user)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="startup_report.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 60

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"Startup Idea Report for {user.username}")
    y -= 30

    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Email: {user.email}")
    y -= 20
    p.drawString(50, y, f"Total Submissions: {submissions.count()}")
    y -= 30

    if not submissions:
        p.drawString(50, y, "No submissions found.")
    else:
        for i, submission in enumerate(submissions, 1):
            if y < 200:
                p.showPage()
                y = height - 60

            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y, f"Entry {i}")
            y -= 20

            p.setFont("Helvetica", 12)
            p.drawString(60, y, f"Startup Idea: {submission.startup_idea}")
            y -= 20
            p.drawString(60, y, f"Business Domain: {submission.get_business_domain_display()}")
            y -= 20
            p.drawString(60, y, f"Problem Statement: {submission.problem_statement}")
            y -= 20
            p.drawString(60, y, f"Business Goal: {submission.business_goal}")
            y -= 20
            p.drawString(60, y, f"Monetization Strategy: {submission.monetization_strategy}")
            y -= 20
            p.drawString(60, y, f"Social Impact: {submission.social_impact}")
            y -= 20
            p.drawString(60, y, f"Timeline: {submission.timeline}")
            y -= 20

            # AI Analysis Section
            p.setFont("Helvetica-Bold", 12)
            p.drawString(60, y, "AI Analysis:")
            y -= 20
            p.setFont("Helvetica", 12)
            p.drawString(70, y, f"Feasibility Level: {submission.feasibility_level}")
            y -= 20
            p.drawString(70, y, f"Feasibility Score: {submission.feasibility_score}")
            y -= 20

            used_tip = "Yes" if submission.monetization_suggestion else "No"
            p.drawString(70, y, f"Monetization Tips Used: {used_tip}")
            y -= 20

            feedback = submission.feasibility_comment if submission.feasibility_comment else "No feedback"
            p.drawString(70, y, f"Feedback: {feedback}")
            y -= 30

            # Separator Line
            p.setStrokeColorRGB(0.6, 0.6, 0.6)
            p.setLineWidth(0.5)
            p.line(50, y, width - 50, y)
            y -= 30

    p.save()
    return response


# ====================== PROFILE ======================
@login_required
def profile_view(request):
    user = request.user
    submissions = Validate_form.objects.filter(user=user)
    validated_count = submissions.filter(feasibility_level="High").count()
    avg_score = submissions.aggregate(Avg('feasibility_score'))['feasibility_score__avg'] or 0
    monetization_used = "Yes" if submissions.filter(monetization_suggestion__isnull=False).exists() else "No"
    feedback_received = submissions.filter(feasibility_comment__isnull=False).count()

    context = {
        "user": user,
        "submission_count": submissions.count(),
        "validated_ideas": validated_count,
        "avg_score": round(avg_score, 2),
        "monetization_used": monetization_used,
        "feedback_received": feedback_received,
        "linkedin_url": "#",
        "github_url": "#",
    }
    return render(request, "dashboard/profile.html", context)


@login_required
def edit_profile(request):
    user = request.user
    error_message = None
    success_message = None

    if request.method == 'POST':
        new_username = request.POST.get('username').strip()
        new_email = request.POST.get('email').strip()
        first_name = request.POST.get('first_name').strip()
        last_name = request.POST.get('last_name').strip()

        if User.objects.exclude(id=user.id).filter(username=new_username).exists():
            error_message = "⚠️ Username already taken by another user."
        elif User.objects.exclude(id=user.id).filter(email=new_email).exists():
            error_message = "⚠️ Email already in use by another user."
        else:
            user.username = new_username
            user.email = new_email
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            success_message = "✅ Profile updated successfully!"

    context = {
        "user": user,
        "error_message": error_message,
        "success_message": success_message
    }
    return render(request, "dashboard/edit_profile.html", context)


# ====================== CRUD Operations ======================
@login_required
def dashboard(request):
    if request.method == "POST":
        user = request.user
        print("Logged in user:", user)
        startup_idea = request.POST.get("startup_idea")
        business_domain = request.POST.get("business_domain")
        problem_statement = request.POST.get("problem_statement")
        business_goal = request.POST.get("business_goal")
        monetization_strategy = request.POST.get("monetization_strategy")
        social_impact = request.POST.get("social_impact")
        timeline = request.POST.get("timeline")

        form = Validate_form(
            user=request.user,
            startup_idea=startup_idea,
            business_domain=business_domain,
            problem_statement=problem_statement,
            business_goal=business_goal,
            monetization_strategy=monetization_strategy,
            social_impact=social_impact,
            timeline=timeline,
        )
        form.save()

        # Save data to session for later use in SWOT page
        request.session["startup_data"] = {
            "startup_idea": startup_idea,
            "business_domain": business_domain,
            "problem_statement": problem_statement,
            "business_goal": business_goal,
            "monetization_strategy": monetization_strategy,
            "social_impact": social_impact,
            "timeline": timeline
        }

        return redirect("dashboard:swot")

    return render(request, "dashboard/dashboard.html")


@login_required
def history(request):
    entries = Validate_form.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "dashboard/history.html", {"submissions": entries})


@login_required
def delete_submission(request, id):
    entry = get_object_or_404(Validate_form, id=id, user=request.user)
    if request.method == "POST":
        entry.delete()
        messages.success(request, "Submission deleted.")
    return redirect('dashboard:history')


@login_required
def update_message(request, id):
    entry = get_object_or_404(Validate_form, id=id, user=request.user)
    if request.method == "POST":
        entry.startup_idea = request.POST.get("startup_idea")
        entry.business_domain = request.POST.get("business_domain")
        entry.problem_statement = request.POST.get("problem_statement")
        entry.business_goal = request.POST.get("business_goal")
        entry.monetization_strategy = request.POST.get("monetization_strategy")
        entry.social_impact = request.POST.get("social_impact")
        entry.timeline = request.POST.get("timeline")
        entry.save()
        messages.success(request, "Submission updated successfully.")
        return redirect("dashboard:swot")
    return render(request, "dashboard/update.html", {'entry': entry})


# ====================== AI ANALYSIS VIEWS ======================
@login_required
def swot(request):
    startup_data = request.session.get("startup_data")

    # If no session data, try to load from the latest database entry
    if not startup_data:
        latest_entry = Validate_form.objects.filter(user=request.user).order_by('-created_at').first()
        if latest_entry:
            startup_data = {
                "startup_idea": latest_entry.startup_idea,
                "business_domain": latest_entry.business_domain,
                "problem_statement": latest_entry.problem_statement,
                "business_goal": latest_entry.business_goal,
                "monetization_strategy": latest_entry.monetization_strategy,
                "social_impact": latest_entry.social_impact,
                "timeline": latest_entry.timeline
            }
            # Save to session for future use
            request.session["startup_data"] = startup_data
        else:
            return redirect("dashboard:dashboard")

    idea = startup_data.get('startup_idea', '')
    domain = startup_data.get('business_domain', '')
    problem = startup_data.get('problem_statement', '')
    goal = startup_data.get('business_goal', '')
    monetization = startup_data.get('monetization_strategy', '')
    social_impact = startup_data.get('social_impact', '')
    timeline = startup_data.get('timeline', '')

    prompt = f"""
IMPORTANT: Do NOT include triple backticks or markdown. Output clean HTML only.

Based on the following startup details, provide a SWOT Analysis in HTML boxes:

Idea: {idea}
Domain: {domain}
Problem: {problem}
Goal: {goal}
Monetization: {monetization}
Social Impact: {social_impact}
Timeline: {timeline}

FORMAT REQUIREMENTS:
- Wrap each section in a <div class="swot-box swot-[type]"> with proper class:
  - swot-strength, swot-weakness, swot-opportunity, swot-threat.
- Each section should have <h2> and a <ul><li> list.
- Example:
  <div class="swot-box swot-strength">
    <h2>Strengths</h2>
    <ul><li>Point 1</li><li>Point 2</li></ul>
  </div>
- Use clean business language and avoid robotic phrasing.
- NO markdown, NO ```html.

Now generate only the HTML.
"""

    swot_text = generate_response(prompt)

    # Strip markdown markers if accidentally added
    if swot_text.startswith("```html"):
        swot_text = swot_text.replace("```html", "").strip()
    if swot_text.endswith("```"):
        swot_text = swot_text.rsplit("```", 1)[0].strip()

    # Save SWOT to latest entry
    latest_entry = Validate_form.objects.filter(user=request.user).order_by('-created_at').first()
    if latest_entry:
        latest_entry.swot_analysis = swot_text
        latest_entry.save()

    return render(request, "dashboard/swot.html", {"swot_raw": swot_text})


# === Feasibility View ===
@login_required
def feasibility(request):
    startup_data = request.session.get("startup_data")
    if not startup_data:
        return redirect("dashboard:dashboard")

    idea = startup_data.get('startup_idea', '')
    domain = startup_data.get('business_domain', '')
    problem = startup_data.get('problem_statement', '')
    goal = startup_data.get('business_goal', '')
    monetization = startup_data.get('monetization_strategy', '')
    impact = startup_data.get('social_impact', '')
    timeline = startup_data.get('timeline', '')

    prompt = f"""
IMPORTANT: Give output ONLY JSON. NO HTML, NO markdown.

Startup Details:
Idea: {idea}
Domain: {domain}
Problem: {problem}
Goal: {goal}
Monetization: {monetization}
Impact: {impact}
Timeline: {timeline}

JSON FORMAT:
{{
  "score": 82,
  "level": "HIGH",
  "emoji": "🟢",
  "summary": "This feasibility score reflects...",
  "market_demand": {{
    "level": "HIGH",
    "emoji": "🟢",
    "text": "The market is highly receptive..."
  }},
  "competition": {{
    "level": "MEDIUM",
    "emoji": "🟡",
    "text": "Moderate competition exists..."
  }},
  "technical_feasibility": {{
    "level": "HIGH",
    "emoji": "🟢",
    "text": "Technology requirements are easy..."
  }},
  "financial_feasibility": {{
    "level": "LOW",
    "emoji": "🔴",
    "text": "Financial risks are present..."
  }}
}}
"""

    raw_response = generate_response(prompt)

    # Fix: Remove ```json and ``` if present
    if raw_response.startswith("```json"):
        raw_response = raw_response.replace("```json", "").strip()
    if raw_response.endswith("```"):
        raw_response = raw_response.rsplit("```", 1)[0].strip()

    print("CLEANED AI RESPONSE:\n", raw_response)

    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        data = {
            "score": 0, "level": "N/A", "emoji": "⚠️", "summary": "⚠️ Error parsing AI response.",
            "market_demand": {"level": "N/A", "emoji": "⚠️", "text": "No data"},
            "competition": {"level": "N/A", "emoji": "⚠️", "text": "No data"},
            "technical_feasibility": {"level": "N/A", "emoji": "⚠️", "text": "No data"},
            "financial_feasibility": {"level": "N/A", "emoji": "⚠️", "text": "No data"},
        }

    # Save to database
    latest_entry = Validate_form.objects.filter(user=request.user).order_by('-created_at').first()
    if latest_entry:
        latest_entry.feasibility_score = data.get('score')
        latest_entry.feasibility_level = data.get('level')
        latest_entry.feasibility_comment = data.get('summary')
        latest_entry.save()

    return render(request, "dashboard/feasibility_score.html", {"data": data})


@login_required
def monetization(request):
    startup_data = request.session.get("startup_data")

    if not startup_data:
        return redirect("dashboard:dashboard")

    idea = startup_data.get('startup_idea', '')
    domain = startup_data.get('business_domain', '')
    problem = startup_data.get('problem_statement', '')
    goal = startup_data.get('business_goal', '')
    monetization_strategy = startup_data.get('monetization_strategy', '')
    impact = startup_data.get('social_impact', '')
    timeline = startup_data.get('timeline', '')

    prompt = f"""
IMPORTANT: Output ONLY HTML. No markdown. No ```html.

Based on the startup info below, give a revenue model analysis with strategies.

Startup Details:
Idea: {idea}
Domain: {domain}
Problem: {problem}
Goal: {goal}
Monetization Strategy: {monetization_strategy}
Impact: {impact}
Timeline: {timeline}

FORMAT:
<div class="revenue-box">
  <h3>Suggested Revenue Model</h3>
  <p>...</p>
</div>

<div class="revenue-box">
  <h3>Pricing Strategy</h3>
  <p>...</p>
</div>

<div class="revenue-box">
  <h3>Financial Risks</h3>
  <p>...</p>
</div>

Keep tone professional and concise. Just output clean HTML for these 3 boxes.
"""

    monetization_html = generate_response(prompt)

    # Clean any markdown markers if accidentally included
    if monetization_html.startswith("```html"):
        monetization_html = monetization_html.replace("```html", "").strip()
    if monetization_html.endswith("```"):
        monetization_html = monetization_html.rsplit("```", 1)[0].strip()

    latest_entry = Validate_form.objects.filter(user=request.user).order_by('-created_at').first()
    if latest_entry:
        latest_entry.monetization_suggestion = monetization_html
        latest_entry.save()

    return render(request, "dashboard/monetization.html", {"monetization_html": monetization_html})


@login_required
def risk(request):
    startup_data = request.session.get("startup_data")

    if not startup_data:
        return redirect("dashboard:dashboard")

    idea = startup_data.get('startup_idea', '')
    domain = startup_data.get('business_domain', '')
    problem = startup_data.get('problem_statement', '')
    goal = startup_data.get('business_goal', '')
    monetization = startup_data.get('monetization_strategy', '')
    impact = startup_data.get('social_impact', '')
    timeline = startup_data.get('timeline', '')

    prompt = f"""
IMPORTANT: Output only clean HTML. No markdown.

Startup Details:
Idea: {idea}
Domain: {domain}
Problem: {problem}
Goal: {goal}
Monetization: {monetization}
Impact: {impact}
Timeline: {timeline}

FORMAT:
<div class="risk-item">
  <h3>🔹 Financial Risk – HIGH 🔴</h3>
  <p>Reasoning text...</p>
</div>
Repeat for: Technical Risk, Market Risk, Operational Risk.
Wrap all in one div class="risk-wrapper".
"""

    raw_html = generate_response(prompt)

    latest_entry = Validate_form.objects.filter(user=request.user).order_by('-created_at').first()
    if latest_entry:
        latest_entry.risk_score = "N/A"
        latest_entry.risk_comment = raw_html
        latest_entry.save()

    return render(request, "dashboard/risk.html", {"risk_html": raw_html})

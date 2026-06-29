import pytest
from core.models import Job
from engines.resume.selector import ResumeSelector
from engines.filter.eligibility import EligibilityFilter
from engines.forms.mapper import FormMapper
from engines.forms.detector import FieldGroup
from engines.forms.question_handler import QuestionClassifier, QuestionHandler

def test_resume_selector():
    selector = ResumeSelector()
    
    # ML-heavy job
    job_ml = Job(
        title="Computer Vision Scientist",
        description="We are looking for someone with PyTorch, TensorFlow, deep learning, NLP, and model training experience.",
        requirements="Required: PyTorch, Transformer models."
    )
    selector.select(job_ml)
    assert job_ml.resume_used == "Resume.pdf"
    
    # Fullstack job
    job_fs = Job(
        title="Web Developer",
        description="Requires Javascript, HTML, CSS, React, and FastAPI.",
        requirements="FastAPI backend and React frontend."
    )
    selector.select(job_fs)
    assert job_fs.resume_used == "Resume.pdf"

def test_eligibility_filter():
    filt = EligibilityFilter()
    
    # High score job
    job_good = Job(
        title="FastAPI Backend Engineer",
        description="We write clean Python code using FastAPI and deploy to AWS docker containers.",
        requirements="Python, FastAPI, AWS, Docker."
    )
    filt.score_job(job_good)
    assert job_good.score >= 5
    assert job_good.would_apply is True
    
    # Bad score job
    job_bad = Job(
        title="PHP WordPress Developer",
        description="Looking for an experienced WordPress dev with PHP and jQuery.",
        requirements="PHP, WordPress, jQuery."
    )
    filt.score_job(job_bad)
    assert job_bad.score < 5
    assert job_bad.would_apply is False

def test_question_classifier():
    assert QuestionClassifier.classify("What is your preferred pronoun?") == "PRONOUNS"
    assert QuestionClassifier.classify("Do you identify as male, female, or non-binary?") == "GENDER"
    assert QuestionClassifier.classify("Are you legally authorized to work in the United States?") == "WORK_AUTHORIZATION"
    assert QuestionClassifier.classify("Will you now or in the future require visa sponsorship?") == "VISA"
    assert QuestionClassifier.classify("Are you willing to relocate?") == "RELOCATION"
    assert QuestionClassifier.classify("What is your desired salary?") == "SALARY"
    assert QuestionClassifier.classify("How many years of experience do you have with Python?") == "EXPERIENCE"

class MockLocator:
    def __init__(self, page=None):
        self.page = page

class MockPage:
    pass

def test_form_mapper():
    mapper = FormMapper()
    
    # Standard profile fields
    fg_resume = FieldGroup(locator=MockLocator(), label="Resume", field_type="file", name_attr="resume")
    fg_email = FieldGroup(locator=MockLocator(), label="Email Address", field_type="email", name_attr="email")
    fg_phone = FieldGroup(locator=MockLocator(), label="Phone", field_type="tel", name_attr="phone")
    fg_first_name = FieldGroup(locator=MockLocator(), label="First Name", field_type="text", name_attr="first_name")
    
    # Questions
    fg_visa = FieldGroup(locator=MockLocator(), label="Do you require visa sponsorship?", field_type="select", name_attr="visa")
    fg_clearance = FieldGroup(locator=MockLocator(), label="Do you have an active security clearance?", field_type="select", name_attr="clearance")
    
    fgs = [fg_resume, fg_email, fg_phone, fg_first_name, fg_visa, fg_clearance]
    profile, questions = mapper.map_fields(fgs)
    
    assert "resume" in profile
    assert "email" in profile
    assert "phone" in profile
    assert "first_name" in profile
    
    assert "Do you require visa sponsorship?" in questions
    assert "Do you have an active security clearance?" in questions

def test_flexible_location_filter():
    INDIA_LOCATIONS = [
        "india",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "pune",
        "chennai",
        "mumbai",
        "gurgaon",
        "gurugram",
        "noida",
        "delhi",
        "remote - india",
    ]
    
    def check_match(loc):
        loc_lower = loc.lower()
        return any(token in loc_lower for token in INDIA_LOCATIONS)
        
    # Match cases
    assert check_match("Hyderabad, India") is True
    assert check_match("Bengaluru, Karnataka") is True
    assert check_match("Pune, Maharashtra") is True
    assert check_match("Delhi, NCR") is True
    assert check_match("Remote - India") is True
    assert check_match("Mumbai, Maharashtra") is True
    
    # Non-match cases
    assert check_match("San Francisco, CA") is False
    assert check_match("London, United Kingdom") is False
    assert check_match("Toronto, Canada") is False


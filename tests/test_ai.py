import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch
import json

from ai.groq_client import GroqClient
from ai.cache import AICache
from ai.validator import AIValidator
from ai.analyzer import AIAnalyzer
from ai.resume_ranker import AIResumeRanker
from ai.cover_letter import AICoverLetterGenerator
from ai.question_answerer import AIQuestionAnswerer

class TestGroqAI(unittest.TestCase):
    def setUp(self):
        # Initialize dependencies with live caching disabled or mocked
        self.mock_client = MagicMock()
        self.mock_client.cache_enabled = False
        
        self.cache = AICache(enabled=False)
        self.validator = AIValidator(self.mock_client)
        
        self.resume_text = "Experienced Backend Python Engineer. Skills: Django, Flask, SQLAlchemy, PostgreSQL, AWS."
        self.profile = {
            "name": "Nivritha Pola",
            "email": "nivritha.pola@gmail.com",
            "phone": "9999999999",
            "education": "B.Tech in Computer Science"
        }

    def test_cache_set_get(self):
        # Test cache operations using standard cache
        cache = AICache(cache_file="data/test_ai_cache.json", enabled=True)
        # Clean test cache if exists
        if os.path.exists("data/test_ai_cache.json"):
            os.remove("data/test_ai_cache.json")
            
        cache.set("Google", "SWE", "cover_letter", "backend.pdf", {"text": "mock cover letter"})
        val = cache.get("Google", "SWE", "cover_letter", "backend.pdf")
        self.assertIsNotNone(val)
        self.assertEqual(val["text"], "mock cover letter")
        
        # Cleanup
        if os.path.exists("data/test_ai_cache.json"):
            os.remove("data/test_ai_cache.json")

    def test_validator_pass(self):
        # Mock validation returning valid
        self.mock_client.call_groq.return_value = '{"valid": true, "reason": "Passed"}'
        validator = AIValidator(self.mock_client)
        
        is_valid = validator.validate("Mocked cover letter.", self.resume_text, str(self.profile))
        self.assertTrue(is_valid)

    def test_validator_fail(self):
        # Mock validation returning invalid
        self.mock_client.call_groq.return_value = '{"valid": false, "reason": "Fabricated Google SDE experience"}'
        validator = AIValidator(self.mock_client)
        
        is_valid = validator.validate("I worked as an SDE at Google.", self.resume_text, str(self.profile))
        self.assertFalse(is_valid)

    def test_analyzer(self):
        analyzer_response = {
            "match_score": 90,
            "reasoning": "Strong alignment.",
            "strengths": ["Python", "SQLAlchemy"],
            "missing_skills": [],
            "recommended_resume": "backend",
            "should_apply": True
        }
        self.mock_client.call_groq.return_value = json.dumps(analyzer_response)
        
        analyzer = AIAnalyzer(self.mock_client, self.cache)
        res = analyzer.analyze_job(
            job_title="Python Developer",
            company="Stripe",
            job_description="Looking for Python developer.",
            job_skills="Python, SQL",
            job_requirements="3+ years Python",
            candidate_profile=self.profile,
            resumes_data={"backend": {"skills": ["Python"]}}
        )
        self.assertEqual(res["match_score"], 90)
        self.assertTrue(res["should_apply"])
        self.assertEqual(res["recommended_resume"], "backend")

    @patch("PyPDF2.PdfReader")
    def test_resume_ranker(self, mock_pdf_reader):
        # Mock pdf extraction
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF text content"
        mock_pdf_reader.return_value.pages = [mock_page]

        ranker_response = {
            "resume": "backend",
            "confidence": 95,
            "reason": "Match skills"
        }
        self.mock_client.call_groq.return_value = json.dumps(ranker_response)
        
        ranker = AIResumeRanker(self.mock_client, self.cache)
        ranker.resumes_config = {
            "backend": {"resume": "Resume.pdf", "skills": ["Python"]}
        }
        
        with patch("os.path.exists", return_value=True), patch("builtins.open", unittest.mock.mock_open()):
            res = ranker.rank_resumes("Job description context", "Company", "Role")
            
        self.assertEqual(res["resume"], "backend")
        self.assertEqual(res["confidence"], 95)

    def test_cover_letter_generator(self):
        self.mock_client.call_groq.return_value = "This is a cover letter."
        
        # Mock validator to pass
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        
        generator = AICoverLetterGenerator(self.mock_client, mock_validator, self.cache)
        letter, attempts = generator.generate("SDE", "Amazon", "JD description", self.resume_text, self.profile)
        self.assertEqual(letter, "This is a cover letter.")
        self.assertEqual(attempts, 1)

    def test_question_answerer(self):
        self.mock_client.call_groq.return_value = "Django, Flask"
        
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        
        qa = AIQuestionAnswerer(self.mock_client, mock_validator, self.cache)
        ans = qa.answer_question("What frameworks do you know?", "text", "SDE role description", self.resume_text, self.profile, "Uber", "SDE")
        self.assertEqual(ans, "Django, Flask")

    def test_form_assistant_fallback(self):
        assistant_response = {
            "answer": "Notice period: 1 month",
            "confidence": 90,
            "reason": "inferred from profile"
        }
        self.mock_client.call_groq.return_value = json.dumps(assistant_response)
        
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        
        qa = AIQuestionAnswerer(self.mock_client, mock_validator, self.cache)
        res = qa.form_assistant_fallback(
            label="Notice period",
            placeholder="1 month",
            question="What is notice period?",
            html_context="<input>",
            job_description="Job desc",
            resume_text=self.resume_text,
            profile_details=self.profile,
            company="Netflix",
            role="Engineer"
        )
        self.assertEqual(res["answer"], "Notice period: 1 month")

if __name__ == "__main__":
    unittest.main()

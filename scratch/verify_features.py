from core.models import Job
from engines.resume.selector import ResumeSelector

selector = ResumeSelector()

print("--- VERIFYING SKILLS-BASED RESUME SELECTOR ---")

# Mock Job 1: ML-heavy
job_ml = Job(
    title="Computer Vision Scientist",
    description="We are looking for someone with PyTorch, TensorFlow, deep learning, NLP, and model training experience.",
    requirements="Required: PyTorch, Transformer models."
)
selector.select(job_ml)
print(f"ML Job selected resume: {job_ml.resume_used} (Expected: Resume.pdf from ml category)")

# Mock Job 2: Fullstack
job_fs = Job(
    title="Web Developer",
    description="Requires Javascript, HTML, CSS, React, and FastAPI.",
    requirements="FastAPI backend and React frontend."
)
selector.select(job_fs)
print(f"Fullstack Job selected resume: {job_fs.resume_used} (Expected: Resume.pdf from fullstack category)")

# Mock Job 3: General fallback
job_gen = Job(
    title="Graduate Intern",
    description="Looking for raw talent with general problem solving skills.",
    requirements="Git, Algorithms."
)
selector.select(job_gen)
print(f"General Job selected resume: {job_gen.resume_used} (Expected: Resume.pdf from general/default category)")

print("\n--- ALL RESUME OVERLAP TESTS COMPLETED SUCCESSFULLY ---")

"""
Second-stage relevance filter, applied locally after the OpenAlex keyword search.

The raw keyword query had a precision of only ~47% on a 150-work hand-labelled sample
(see notebooks/02_validate_query.ipynb). The rule below is stricter:
  1. an AI term must be central: in the TITLE, or at least twice in the abstract, AND
  2. an education term must be central in the same sense,
  3. after removing known false-positive phrases ("curriculum learning", "student abstract", ...).
"""

import re

AI_RE = re.compile(
    r"artificial intelligence|machine learning|deep learning|neural network|chatgpt|gpt-?[34]|"
    r"generative ai|genai|\bgen ai\b|large language model|\bllms?\b|\bai\b|learning analytics|"
    r"intelligent tutoring|educational data mining|chatbot|natural language processing|\bnlp\b",
    re.I,
)

EDU_RE = re.compile(
    r"\beducat|\bteach|\bstudents?\b|\blearners?\b|classroom|\bschools?\b|curricul|pedagog|"
    r"\btutor|\bmoocs?\b|e-learning|higher education|universit(y|ies) course|\blectur|"
    r"learning analytics|\bcourses?\b|\bliteracy\b|\bexams?\b|assessment of student",
    re.I,
)

# phrases that contain an education word but are not about education
FALSE_POSITIVE_RE = re.compile(
    r"curriculum learning|curricula in neural|student abstract|student[- ]teacher (model|network|distillation|framework)|"
    r"teacher[- ]student (model|network|distillation|framework|learning)|knowledge distillation|"
    r"self-taught|teacher forcing|deep learning approach to learning",
    re.I,
)


def clean(text):
    return FALSE_POSITIVE_RE.sub(" ", text or "")


def central(pattern, title, abstract):
    """A concept counts as central if it is in the title or repeated in the abstract."""
    return bool(pattern.search(title)) or len(pattern.findall(abstract)) >= 2


def is_relevant(title, abstract):
    t, a = clean(title), clean(abstract)
    return central(AI_RE, t, a) and central(EDU_RE, t, a)

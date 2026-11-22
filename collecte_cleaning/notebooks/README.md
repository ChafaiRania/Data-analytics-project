# Two notebooks for `collecte_cleaning/`

Copy the content of this folder into `collecte_cleaning/` (same layout):

```
collecte_cleaning/
  notebooks/02_validate_query.ipynb     <- RQ4: precision / recall of the search and the relevance rule
  notebooks/02_all_vs_strict.ipynb      <- RQ2: ALL vs STRICT (re-created, see its first cell)
  data/validation/relevance_labels.csv  <- the 284 labelled papers
```

Run them from `collecte_cleaning/notebooks/` with Jupyter. They read `data/processed/` and `src/clean.py`
(Person 1's code, unchanged) and write nothing. Both were executed without errors; the saved outputs are
in the files.

## Team check of the labels (please do this)

The first labels in `relevance_labels.csv` were made by Claude (AI) from title and abstract. Two members
should each fill one column, `label_member_a` and `label_member_b`, with yes / no / unsure, without looking at
each other's column. Then re-run `02_validate_query.ipynb`. Where both members agree, their label replaces the
AI label, and the notebook reports agreement.

Rule: **yes** = AI is studied in an education context (teaching, learning, students, teachers, curricula,
assessment, educational institutions; medical education included). **no** = education is incidental (patient
education, students only as survey respondents, "teacher-student" networks). **unsure** = title and abstract do
not decide it.

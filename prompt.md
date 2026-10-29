# Project prompt: Assignment Lifecycle and Grading Management System

## Project technology stack

* Frontend: React + Vite + Tailwind CSS
* Backend: Python + FastAPI
* Database: SQLite
* ORM: SQLAlchemy 2.0
* Migrations: Alembic
* Validation: Pydantic
* Data generation: Faker, NumPy, pandas
* Testing: Pytest + HTTPX
* Charts: Recharts

---

## Step 1: Architecture and requirements analysis

Act as a senior full-stack developer and software architect. I want to build an Assignment Lifecycle and Grading Management System.

Use React, Vite, Tailwind CSS, Python, FastAPI, SQLAlchemy 2.0, SQLite, Alembic, and Pydantic.
The application must manage:

* Courses and learner enrollments
* Assignment creation and publication
* Rubrics and rubric criteria
* Submissions and artifact metadata
* Rubric-based grading and feedback
* Resubmissions and late penalties
* Appeals and grade revisions
* Audit history and lifecycle transitions
* Synthetic data generation and validation
* Analytics dashboards and exports

Actors:
Learner, instructor, academic administrator, support staff, and platform administrator.
First, analyze the requirements and create:

1. System architecture.
2. Mermaid entity relationship diagram.
3. Complete entity and relationship list.
4. API endpoint plan.
5. Role-based permission matrix.
6. Folder structure.
7. Business workflow diagrams.
8. Development milestones and acceptance criteria.

Do not write application code yet. Identify missing requirements and propose sensible defaults. Wait for my approval before moving to Step 2.

---

## Step 2: Initial project structure

Based on the approved architecture, create the initial project structure.
Frontend:

* React with Vite.
* Tailwind CSS.
* Axios.
* React Router.
* Recharts.
* Lucide React icons.

Backend:

* Python.
* FastAPI.
* Uvicorn.
* SQLAlchemy 2.0.
* Alembic.
* Pydantic and pydantic-settings.
* SQLite.
* Pytest and HTTPX.

Create the frontend and backend folders, Python virtual environment, requirements.txt, package.json, .env.example, and .gitignore.
Requirements:

1. Keep frontend and backend separate.
2. Create a minimal FastAPI application with a health-check endpoint.
3. Create a minimal React application with a home page.
4. Configure CORS for local development.
5. Configure SQLite using DATABASE_URL=sqlite:///./assignment_management.db.
6. Keep secrets and local database files out of Git.
7. Add commands for installation, startup, and testing on Windows PowerShell.

Provide the exact terminal commands and complete contents of every initial file. Verify that both applications start successfully before continuing.

---

## Step 3: Database schema and migrations

Implement the database schema using SQLAlchemy 2.0, SQLite, and Alembic.
Create models for:

1. Course
2. Learner
3. CourseEnrollment
4. Assignment
5. AssignmentVersion
6. Rubric
7. RubricCriterion
8. Submission
9. SubmissionArtifact
10. Grade
11. RubricScore
12. GradeRevision
13. Feedback
14. Resubmission
15. Appeal
16. AuditEvent

For every field, document its type, required/optional status, allowed values, units, uniqueness, default, and validation rule.
Requirements:

* Define primary keys and foreign keys.
* Define one-to-many and many-to-many relationships.
* Add unique constraints and indexes.
* Enable SQLite foreign-key enforcement on every database connection.
* Use appropriate numeric types for scores and penalties.
* Store timestamps in UTC and use timezone-aware application-level comparisons.
* Define lifecycle states and valid transitions.
* Preserve assignment versions, submission versions, grade revisions, and audit history.
* Use Alembic migrations rather than relying only on create_all().
* Create a data dictionary and Mermaid ER diagram.
* Add tests for relationships, constraints, and invalid records.

Provide complete files and commands. Run migrations and tests where possible. Do not generate large datasets yet.

---

## Step 4: Authentication and authorization

Implement authentication and authorization for the FastAPI application.
Roles:

* Learner
* Instructor
* Academic administrator
* Support staff
* Platform administrator

Requirements:

1. Create registration and login endpoints.
2. Hash passwords securely using pwdlib with Argon2.
3. Implement JWT access-token authentication.
4. Add a reusable FastAPI dependency to retrieve the current authenticated user.
5. Implement role-based authorization dependencies.
6. Prevent learners from grading their own work or accessing other learners' private submissions.
7. Restrict publication, grading, appeal decisions, and administrative actions to authorized roles.
8. Validate all permissions on the backend.
9. Add safe error responses and input validation.
10. Write Pytest and HTTPX tests for authentication, authorization, and invalid access.

Use SQLite and the existing SQLAlchemy models. Include any necessary migrations. Explain how to create test accounts and demonstrate the endpoints through FastAPI Swagger UI.

---

## Step 5: Course, learner, enrollment, assignment, rubric and publication workflows

Implement the course, learner, enrollment, assignment, rubric, and publication workflows.
Create REST APIs for:

* Course CRUD operations.
* Learner management.
* Course enrollment.
* Assignment CRUD operations.
* Rubric and criterion management.
* Assignment publication and version history.

Requirements:

1. Validate parent IDs and relationships.
2. Prevent duplicate enrollments.
3. Require a valid rubric before assignment publication.
4. Validate due dates and publication times.
5. Store published assignment versions so historical submissions can be interpreted correctly.
6. Prevent invalid lifecycle transitions.
7. Use Pydantic request and response schemas.
8. Use service-layer functions for business logic.
9. Use database transactions for multi-record operations.
10. Add pagination, filtering, and centralized error handling.

Create automated tests for successful operations, invalid parent IDs, duplicate enrollment, invalid deadlines, and unauthorized publication. Demonstrate a complete workflow using the API.

---

## Step 6: Submission, artifact, grading and feedback workflows

Implement the submission, artifact, grading, and feedback workflows.
Submission requirements:

* Accept submissions only from enrolled learners.
* Validate assignment publication status and deadline.
* Record submission timestamps and version numbers.
* Store artifact filename, MIME type, file size, checksum, upload timestamp, and availability status.
* Preserve every submission version.

Grading requirements:

* Grade submissions using the assignment's published rubric version.
* Validate each criterion score against its maximum.
* Calculate the raw score from criterion-level scores.
* Apply late penalties only when the documented policy requires them.
* Apply each penalty at most once per applicable submission version.
* Calculate the final score from the raw score and penalty using documented rounding rules.
* Record grader identity, feedback, timestamps, and grade revisions.
* Preserve earlier grades and feedback.

Use SQLAlchemy transactions and appropriate uniqueness constraints. Do not overwrite previous versions.
Create tests for on-time submissions, late submissions, missing artifacts, invalid scores, duplicate penalties, and grade reconciliation. Explain the workflow and provide example API requests and responses.

---

## Step 7: Resubmission and appeal workflows

Implement the resubmission and appeal workflows.
Resubmission requirements:

1. Check the assignment's resubmission policy.
2. Enforce eligibility and attempt limits.
3. Link each resubmission to the previous submission.
4. Record request timestamps, decisions, and resulting submission versions.
5. Preserve prior grades and artifacts.

Appeal requirements:

1. Allow appeals only for eligible grade versions.
2. Record appeal reason, supporting evidence references, reviewer, status, decision, and timestamps.
3. Support approved, rejected, and upheld outcomes according to a clearly documented decision model.
4. Require a reason for every grade change.
5. Preserve original grades and all grade revisions.
6. Record an audit event for every appeal decision and grade change.
7. Ensure the grade change and its audit record are committed atomically.

Use FastAPI, SQLAlchemy, SQLite transactions, and Pydantic validation.
Add tests for denied resubmissions, exhausted attempts, duplicate appeals, upheld grades, changed grades, unauthorized reviewers, and missing audit events. Do not allow an appeal to modify a grade without traceable history.

---

## Step 8: Synthetic data generator

Create a configurable synthetic-data generator using Python, Faker, NumPy, pandas, and the existing SQLAlchemy models.
Use the fixed seed 20261022.
Full dataset targets:

* 1,000 assignments.
* 10,000 learners.
* 30,000 submissions.

Generate data in this order:

1. Courses and learners.
2. Enrollments.
3. Assignments and assignment versions.
4. Rubrics and rubric criteria.
5. Submissions and artifact metadata.
6. Rubric scores and grades.
7. Feedback and grade revisions.
8. Resubmissions.
9. Appeals and decisions.
10. Audit events.

Requirements:

* Generate valid baseline data before anomalies.
* Generate child records only after valid parent IDs exist.
* Use deterministic, zero-padded identifiers.
* Generate realistic variations in submission times, scores, late work, missing artifacts, resubmissions, and appeal outcomes.
* Calculate scores, penalties, statuses, and metrics from source records.
* Support a small starter dataset and the full dataset through configurable parameters.
* Use the same generation rules for both modes.
* Make regeneration safe and prevent accidental duplicate records.

Create CSV and JSON exports for every entity, plus optional SQL seed data. Store anomaly labels and expected decisions in separate ground_truth.csv and ground_truth.json files.
Include a generator CLI, source manifest, row counts, content checksums, README instructions, and tests proving deterministic generation.

---

## Step 9: Data-quality validation engine

Implement a data-quality validation engine for the generated dataset and application database.
Required anomaly scenarios:

1. Submission belongs to an unenrolled learner.
2. Grade exceeds the rubric maximum.
3. Late penalty is applied twice.
4. Appeal changes a grade without an audit record.

Requirements:

* Keep deliberately invalid fixtures separate from valid baseline data.
* Store issue_type, ground_truth, affected_entity_type, affected_entity_id, expected_behavior, and explanation in the separate ground-truth dataset.
* Validate primary-key uniqueness and foreign-key integrity.
* Check allowed enums, lifecycle transitions, deadline logic, rubric score reconciliation, duplicate penalties, and audit history.
* Detect anomalies independently of the ground-truth labels.
* Compare detected anomalies against ground truth.
* Calculate precision, recall, F1 score, and a confusion matrix when appropriate.
* Distinguish a transaction rejected by the application from an anomaly detected during offline validation.
* Generate a validation report with pass/fail status and examples.

Write automated tests for all four scenarios. Never use ground-truth labels as input features for the anomaly detector.

---

## Step 10: Frontend

Build the React + Vite + Tailwind CSS frontend and connect it to the existing FastAPI backend.
Create pages for:

1. Login and role-aware navigation.
2. Overview dashboard.
3. Courses and enrollments.
4. Learners.
5. Assignment creation and publication.
6. Rubric editor.
7. Learner assignment list.
8. Submission and artifact history.
9. Instructor grading workspace.
10. Feedback and grade revisions.
11. Resubmission management.
12. Appeals and review decisions.
13. Audit trail viewer.
14. Dataset generation and export.
15. Data-quality reports.

Dashboard metrics:

* Total assignments and submissions.
* On-time and late submission rates.
* Missing-artifact rate.
* Pending grading workload.
* Average grading turnaround time.
* Average raw and final grades.
* Resubmission rate and score improvement.
* Appeal rate and outcomes.
* Grade-change rate.
* Data-quality pass rate and anomaly counts.

Requirements:

* Fetch real API data rather than using hardcoded mock data.
* Use Axios through a centralized API client.
* Include pagination, filters, loading states, error messages, and empty states.
* Show grade history and submission versions chronologically.
* Display rubric totals and late penalties transparently.
* Hide unauthorized UI actions while keeping server-side permission checks.
* Build reusable components and responsive layouts.

Implement the dashboard first, then connect and test each workflow page.

---

## Step 11: Evaluation and portfolio demonstration

Prepare the project for evaluation and portfolio demonstration.
Complete:

1. Backend unit and integration tests.
2. Frontend workflow testing.
3. Database migration and initialization tests.
4. Foreign-key and arithmetic validation.
5. Role-based authorization tests.
6. End-to-end submission, grading, resubmission, and appeal tests.
7. Four anomaly scenario tests.
8. CSV, JSON, and SQL export verification.
9. Ground-truth isolation checks.
10. Reproducibility verification.

Run the generator twice with seed 20261022 and compare logical row counts and content checksums for each entity. Exclude generation timestamps and other intentionally variable metadata from logical checksums.
Produce:

* README.md
* ER diagram
* Data dictionary
* API documentation
* Setup and migration instructions
* Generator CLI documentation
* Source manifest
* Validation summary
* Test report
* Example exported data
* Demo walkthrough

Verify that the dataset contains 1,000 assignments, 10,000 learners, and 30,000 submissions. Report actual counts, test results, checksum comparisons, performance observations, and any unresolved issues. Do not claim success for tests or generation steps that were not executed.

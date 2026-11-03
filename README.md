# Online Examination Management System

A Flask and MySQL application for student registration, administrator-managed MCQ examinations, timed attempts, and automatic result calculation. The repository also includes Docker, Jenkins, pytest, and SonarQube configuration for a demonstration CI/CD pipeline.

## Features

- Student registration and sign-in with Werkzeug password hashing.
- Admin dashboard with student counts, exam management, question management, and recent results.
- Question editing, explicit finish-editing and publish controls, and scheduled exam start/end times.
- Student dashboard with available exams and completed results.
- Four-option MCQ attempts with a countdown and automatic submission.
- Server-side answer evaluation. Correct answers are never included in the student question query or template.
- One attempt per student per exam, enforced by a database unique constraint.
- Students can start published examinations only during the configured availability window; the server enforces both the exam duration and scheduled end time.

## Run with Docker Compose

Install Docker Desktop, then from the project root:

```powershell
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_PASSWORD = "change-this-password"
$env:SECRET_KEY = "replace-with-a-long-random-secret"
docker compose up --build
```

Open [http://localhost:5000](http://localhost:5000). The configured administrator can sign in; students register from the sign-in page. The database volume persists between restarts. Set `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` for local development overrides.

## Run locally without Docker

Use Python 3.12 and a MySQL 8 server. Create the `online_exam_db` database and a MySQL user, then install dependencies and configure the environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_USER = "exam_user"
$env:MYSQL_PASSWORD = "your-database-password"
$env:MYSQL_DATABASE = "online_exam_db"
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_PASSWORD = "change-this-password"
flask --app app init-db
flask --app app run --debug
```

`init-db` applies `database/schema.sql` and creates the admin account when both `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set. For CI tests, install dependencies and run `pytest -v`; tests do not require a live database.

## CI/CD configuration

- `Dockerfile` packages the Flask app; `docker-compose.yml` runs MySQL and the app together.
- `Jenkinsfile` checks out the repository, installs dependencies, runs pytest, optionally runs SonarScanner when `SONAR_TOKEN` is configured, builds an image, and deploys the `main` branch to a Docker-capable Jenkins agent.
- Configure a Jenkins SonarQube installation named `SonarQube`, Docker access on the agent, and credentials/environment values `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, and `SECRET_KEY` before enabling deployment. Provide the SonarQube token as a Jenkins secret text binding named `SONAR_TOKEN`.
- A GitHub webhook and Jenkins job are configured in the Jenkins UI; they cannot be provisioned by this repository alone.

The included deployment stage expects MySQL to be reachable from the Jenkins agent and container on the configured `MYSQL_HOST`. For a real deployment, use managed secrets, TLS, a production database, backups, and an explicit release strategy.

Exam start/end values are entered in `APP_TIMEZONE` (defaults to `Asia/Kolkata`) and stored as UTC. Set `APP_TIMEZONE` in the environment if administrators work in another time zone.

## Main routes

| Area | Route |
| --- | --- |
| Student registration and login | `/register`, `/login` |
| Public welcome and signed-in home | `/`, `/home` |
| Public product pages | `/features`, `/how-it-works` |
| Administrator examinations, students, and analytics | `/admin/dashboard`, `/admin/exams/new`, `/admin/students`, `/admin/analytics` |
| Edit, schedule, and publish exams/questions | `/admin/exams/<id>/edit`, `/admin/exams/<id>/questions`, `/admin/exams/<id>/publish`, `/admin/questions/<id>/edit` |
| Individual student history (admin) | `/admin/students/<id>` |
| Examination questions | `/admin/exams/<id>/questions` |
| Student examinations, details, and attempt | `/student/dashboard`, `/exams/<id>`, `/exam/<id>` |
| Student score analysis and results | `/student/analysis`, `/results/<id>` |
| Help and FAQs | `/help` |

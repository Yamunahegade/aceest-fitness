# ACEest Fitness & Gym — Flask API with CI/CD

ACEest Fitness & Gym is a client-management service for a fitness startup. It began as a
Tkinter desktop prototype (v1.0 → v3.2.4, kept in [`legacy/`](legacy/)) and has been ported
to a **Flask REST API** so it can be containerised, tested and deployed through an automated
pipeline (**Git → GitHub Actions → Docker → Jenkins**).

## Features (ported from the desktop versions)
| Area | Origin | What it does |
|---|---|---|
| Programs & calories | v1.0 / v1.1 | Fat Loss (3/5 day), Muscle Gain, Beginner; kcal = weight × program factor |
| Client management | v2.0+ | Create / read / update / delete clients, goals (target weight, adherence) |
| Weekly progress | v2.0+ | Log adherence %, history, average adherence |
| Workouts & exercises | v2.2+ | Log sessions with exercises; history newest-first |
| Body metrics | v2.2+ | Weight / waist / body-fat log; keeps client weight & calories in sync |
| BMI & risk | v2.2.4 | BMI, category and risk note |
| Program generator | v3.1+ | Picks a plan template matching the client's program category |
| Membership | v3.2+ | Status, end date, days remaining |

## API
| Method | Path | Description |
|---|---|---|
| GET | `/`, `/health` | Service info / health check |
| GET | `/programs` | Programs with calorie factors |
| GET, POST | `/clients` | List / create client |
| GET, PUT, DELETE | `/clients/<name>` | Read / update / delete client (+ related records) |
| GET, POST | `/clients/<name>/progress` | Weekly adherence history / log `{"adherence": 0-100}` |
| GET, POST | `/clients/<name>/workouts` | History / log `{"workout_type", "date", "duration_min", "exercises": [...]}` |
| GET, POST | `/clients/<name>/metrics` | History / log `{"date", "weight", "waist", "bodyfat"}` |
| GET | `/clients/<name>/bmi` | BMI, category, risk note |
| GET | `/clients/<name>/summary` | Profile, goals, progress summary, latest metrics |
| POST | `/clients/<name>/generate-program` | Generate a plan template |
| GET, PUT | `/clients/<name>/membership` | Membership status / `{"status", "end_date"}` |

## Project structure
```
app.py                      Flask application (app factory + pure logic functions)
requirements.txt            Runtime dependencies
requirements-dev.txt        + pytest, flake8
tests/                      Pytest suite (logic + API tests, isolated temp DB per test)
Dockerfile                  Production image (multi-stage, non-root, healthcheck)
Dockerfile.test             Image that runs the Pytest suite
Jenkinsfile                 Jenkins pipeline
.github/workflows/main.yml  GitHub Actions pipeline
legacy/                     Original Tkinter versions v1.0 → v3.2.4 (reference only)
```

## Local setup
```bash
git clone <repo-url> && cd <repo>
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py                      # http://localhost:5000  (SQLite file: aceest_fitness.db)
```
Example:
```bash
curl -X POST localhost:5000/clients -H "Content-Type: application/json" \
  -d '{"name":"Asha","height":165,"weight":70,"program":"Fat Loss (FL) - 3 day"}'
curl localhost:5000/clients/Asha/bmi
```
The database location can be changed with the `ACEEST_DB` environment variable.

## Docker
```bash
docker build -t aceest-fitness .
docker run -p 5000:5000 -v aceest_data:/data aceest-fitness
curl localhost:5000/health
```
The image is multi-stage (build deps not shipped), runs as a non-root user, has a
`HEALTHCHECK`, and keeps the SQLite file on the `/data` volume.

## Running the tests manually
```bash
pytest -v                  # all tests
pytest --cov=app           # with coverage (pip install pytest-cov)
flake8 .                   # lint

# Same as CI: inside a container
docker build -f Dockerfile.test -t aceest-fitness-test .
docker run --rm aceest-fitness-test
```
Every test uses its own temporary SQLite database, so tests are independent and leave
no files behind.

## CI/CD overview

### GitHub Actions — `.github/workflows/main.yml`
Runs on every **push** and **pull_request**. Jobs run in sequence; a failure stops the chain.
1. **Build & Lint** — install dependencies, byte-compile (`compileall`) to catch syntax errors, run `flake8`.
2. **Docker Image Assembly** — build the production image, start it and hit `/health` as a smoke test.
3. **Automated Testing** — build `Dockerfile.test` and run Pytest *inside the container*.

### Jenkins — `Jenkinsfile`
Jenkins is the second, independent build gate in a controlled environment:
1. **Checkout** the latest code from GitHub.
2. **Clean** images left from previous builds.
3. **Build** the Docker image with `--no-cache` (a truly clean build).
4. **Quality Gate** — run Pytest in a container; any failing test fails the build.

**Jenkins setup:** run Jenkins with access to the Docker daemon
(`-v /var/run/docker.sock:/var/run/docker.sock`) and the Docker CLI installed, then create a
*Pipeline* job → *Pipeline script from SCM* → Git → this repo → script path `Jenkinsfile`.
Optionally enable *Poll SCM* or a GitHub webhook for automatic builds on push.

## Branching & commits
`main` is always releasable. Work happens on `feature/*`, `bugfix/*` and `infra/*` branches and
is merged through pull requests (which trigger the CI workflow). Commits follow
[Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `test:`, `ci:`, `build:`, `docs:`).

## Known limitations
No authentication (the desktop v3.x login used plaintext passwords and was intentionally not
ported), no PDF export, and SQLite is single-writer — fine for this assignment, not for scale.

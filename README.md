# Playto Pay — KYC Pipeline

A full-stack KYC (Know Your Customer) onboarding pipeline for Playto Pay, built with Django + DRF on the backend and React + Tailwind on the frontend.

## Stack

- **Backend**: Django 4.2, Django REST Framework, SQLite
- **Frontend**: React 18, Tailwind CSS, Vite
- **Auth**: DRF Token Authentication + role field (`merchant` / `reviewer`)

---

## Local Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python seed.py                    # creates test users (see credentials below)
python manage.py runserver
```

Backend runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

---

## Demo Accounts

All demo accounts are created using the `seed.py` script. By default, all accounts use the password: `merchant123` (or `reviewer123` for the reviewer).

| Role     | Username  | Current State  |
|----------|-----------|----------------|
| Reviewer | reviewer1 | [Full Access]  |
| Merchant | merchant1 | **Draft**      |
| Merchant | merchant2 | **In Queue** ⚠ |
| Merchant | merchant3 | **Approved**   |

> [!NOTE]
> `merchant2` is intentionally backdated to demonstrate the **SLA at_risk** flag in the reviewer dashboard.

---

## Running Tests

```bash
cd backend
python manage.py test kyc --verbosity=2
```

18 tests, 0 failures. Covers:
- All legal state transitions pass
- All illegal transitions raise `IllegalTransitionError`
- API returns 400 on illegal transitions with helpful messages
- Merchant isolation (merchant B cannot see merchant A's submission)
- Role enforcement (merchant cannot hit reviewer endpoints)

---

## API Reference (`/api/v1/`)

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register/` | Create merchant or reviewer account |
| POST | `/auth/login/` | Get token |
| GET | `/auth/me/` | Current user |

### Merchant
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/kyc/submission/` | Get own KYC submission |
| PATCH | `/kyc/submission/` | Update draft fields |
| POST | `/kyc/submit/` | Submit for review (draft → submitted) |
| POST | `/kyc/documents/<type>/` | Upload document (pan/aadhaar/bank_statement) |
| DELETE | `/kyc/documents/<type>/` | Remove a document |

### Reviewer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reviewer/queue/` | Active submissions, oldest first |
| GET | `/reviewer/submissions/` | All submissions |
| GET | `/reviewer/submissions/<id>/` | Submission detail |
| POST | `/reviewer/submissions/<id>/transition/` | Change state |
| GET | `/reviewer/metrics/` | Dashboard metrics |

### Shared
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications/` | Notification event log |

---

## Error Shape

All errors return:
```json
{
  "error": true,
  "message": "Cannot transition from 'approved' to 'draft'. Allowed transitions from 'approved': none (terminal state).",
  "detail": { ... }
}
```

---

## Project Structure

```
backend/
  kyc/
    state_machine.py   ← single source of truth for all state transitions
    validators.py      ← file upload validation (type + size + magic bytes)
    models.py          ← User, KYCSubmission, Document, NotificationEvent
    serializers.py     ← DRF serializers
    views.py           ← API views
    permissions.py     ← IsMerchant, IsReviewer, IsSubmissionOwner
    tests.py           ← 18 tests
  seed.py
frontend/
  src/
    pages/
      Auth.jsx               ← Login + Register
      KYC.jsx                ← Multi-step merchant form
      ReviewerDashboard.jsx  ← Queue + metrics
      SubmissionDetail.jsx   ← Review actions
    api.js                   ← Axios API client
    hooks/useAuth.jsx        ← Auth context
```

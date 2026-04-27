# EXPLAINER.md

Answers to the specific technical questions from the challenge brief.

---

## 1. The State Machine

**Where does it live?** `backend/kyc/state_machine.py` — one file, nothing else touches state.

```python
LEGAL_TRANSITIONS: dict[str, list[str]] = {
    "draft":                ["submitted"],
    "submitted":            ["under_review"],
    "under_review":         ["approved", "rejected", "more_info_requested"],
    "more_info_requested":  ["submitted"],
    "approved":             [],
    "rejected":             [],
}

def validate_transition(current_state: str, new_state: str) -> None:
    allowed = LEGAL_TRANSITIONS.get(current_state, [])
    if new_state not in allowed:
        raise IllegalTransitionError(current_state, new_state)

def apply_transition(submission, new_state: str, reviewer_note: str = "") -> str:
    validate_transition(submission.state, new_state)
    old_state = submission.state
    submission.state = new_state
    if new_state == "submitted" and submission.submitted_at is None:
        submission.submitted_at = timezone.now()
    if reviewer_note:
        submission.reviewer_note = reviewer_note
    submission.save(update_fields=["state", "submitted_at", "reviewer_note", "updated_at"])
    return old_state
```

**How do I prevent illegal transitions?** `validate_transition()` is called first inside `apply_transition()`. Every view that changes state calls `apply_transition()` — never `submission.state = "..."` directly. If the transition is not in `LEGAL_TRANSITIONS[current_state]`, it raises `IllegalTransitionError`, which the view catches and returns as a 400 with a message that names the current state, the requested state, and what *is* allowed.

No view imports the `LEGAL_TRANSITIONS` dict or mutates `.state` directly. The dict is the single, auditable list of what the business allows.

---

## 2. The Upload

**How is file validation done?** Three layers, all server-side, in `backend/kyc/validators.py`:

```python
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

FILE_SIGNATURES = {
    b"\x25\x50\x44\x46": "application/pdf",   # %PDF
    b"\xff\xd8\xff":     "image/jpeg",
    b"\x89\x50\x4e\x47": "image/png",
}

def validate_upload(file_obj) -> None:
    # 1. Size
    if file_obj.size > MAX_SIZE_BYTES:
        raise ValidationError(f"File is {file_obj.size / (1024*1024):.1f} MB. Max is 5 MB.")

    # 2. Extension
    _, ext = os.path.splitext(file_obj.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extension '{ext}' not allowed.")

    # 3. Magic bytes — read first 8 bytes to confirm real file type
    file_obj.seek(0)
    header = file_obj.read(8)
    file_obj.seek(0)
    detected = None
    for signature, mimetype in FILE_SIGNATURES.items():
        if header.startswith(signature):
            detected = mimetype
            break
    if detected is None:
        raise ValidationError("File does not appear to be a valid PDF, JPG, or PNG.")

    # 4. Extension must match detected type (catches renamed files)
    ext_to_expected = {".pdf": "application/pdf", ".jpg": "image/jpeg",
                       ".jpeg": "image/jpeg", ".png": "image/png"}
    if detected != ext_to_expected[ext]:
        raise ValidationError("File content does not match its extension. Upload rejected.")
```

**What happens with a 50 MB file?** It fails at check 1 before we touch the content. Django's `InMemoryUploadedFile.size` is set from `Content-Length` — but we also re-check against the actual bytes via `file_obj.size` in the serializer, so a client lying about Content-Length would still fail when the file is parsed. The error returned is 400: `"File is 50.0 MB. Maximum allowed size is 5 MB."` — never a 500 or a silent pass.

---

## 3. The Queue

**The query powering the reviewer dashboard:**

```python
# In ReviewerQueueView.get()
active_states = ["submitted", "under_review", "more_info_requested"]
submissions = (
    KYCSubmission.objects.filter(state__in=active_states)
    .select_related("merchant", "assigned_reviewer")
    .prefetch_related("documents")
    .order_by("submitted_at")   # oldest first
)
```

**SLA flag:**

```python
# model property on KYCSubmission — computed fresh on every read, never stored
@property
def is_at_risk(self) -> bool:
    SLA_HOURS = 24
    at_risk_states = {"submitted", "under_review", "more_info_requested"}
    if self.state not in at_risk_states or self.submitted_at is None:
        return False
    age = timezone.now() - self.submitted_at
    return age.total_seconds() > SLA_HOURS * 3600
```

**Why this way?**

- `select_related` and `prefetch_related` prevent N+1 queries — one JOIN for merchant, one extra query for documents, not one per row.
- `is_at_risk` is a `@property`, not a DB column. A stored `at_risk` flag would go stale the moment the cutoff passed without a job running. The property recomputes from `submitted_at` every time, so it's always accurate.
- `order_by("submitted_at")` — ascending so the oldest (highest priority) submission appears first. NULL `submitted_at` values (drafts) would sort first in PostgreSQL, but drafts are excluded by the `state__in` filter.

The metrics endpoint uses the same principle with `Avg(ExpressionWrapper(now - F("submitted_at"), ...))` to compute average queue age entirely in the database.

---

## 4. The Auth

**How does merchant A's data stay away from merchant B?**

Two layers:

**Layer 1 — Queryset scoping.** Merchants only have one endpoint for their own submission (`/api/v1/kyc/submission/`), and it always filters by `request.user`:

```python
# views.py — MySubmissionView
def _get_submission(self, user):
    return KYCSubmission.objects.get(merchant=user)  # always the current user's
```

There is no endpoint like `/api/v1/kyc/submission/<id>/` that a merchant could enumerate.

**Layer 2 — Role enforcement on reviewer endpoints.** Even if merchant B knew merchant A's submission ID and hit `/api/v1/reviewer/submissions/<id>/`, they'd be blocked by the `IsReviewer` permission:

```python
# permissions.py
class IsReviewer(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "reviewer"
        )
```

A merchant hitting a reviewer endpoint gets 403. No guessing IDs helps — merchants have no route to enumerate.

The `IsSubmissionOwner` object-level permission exists as an additional belt-and-suspenders check on any future endpoint that might be shared:

```python
class IsSubmissionOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == "reviewer":
            return True
        return obj.merchant_id == request.user.id  # strict ID equality, not .merchant == request.user
```

We compare `merchant_id` (the raw FK integer) rather than the full object to avoid any risk of lazy-loading quirks.

---

## 5. The AI Audit

**AI-generated code with a security flaw:**

I asked an AI assistant to generate the file validation logic for the Django backend. It initially suggested a check based primarily on the `content_type` attribute of the uploaded file object:

```python
# AI-generated suggestion (Vulnerable)
def validate_upload(file):
    valid_types = ['application/pdf', 'image/jpeg', 'image/png']
    if file.content_type not in valid_types:
        raise ValidationError("Unsupported file type.")
    if file.size > 5 * 1024 * 1024:
        raise ValidationError("File too large.")
```

**The Catch:**
The `file.content_type` property is derived from the `Content-Type` header sent by the client. It is entirely user-controlled and untrustworthy. A malicious actor could easily rename an executable or script to `document.pdf` and manually set the `Content-Type` header to `application/pdf` in their request. The AI's suggestion would trust this header blindly, allowing potentially harmful files onto the server.

**The Fix:**
I replaced this with a **magic-bytes (file signature) validation** system located in `backend/kyc/validators.py`. 

Instead of trusting the header, the system now:
1.  Reads the first few bytes of the actual file content.
2.  Matches these bytes against known signatures (e.g., `%PDF` for PDFs, fixed hex patterns for JPEGs/PNGs).
3.  Cross-references the detected mime-type with the file extension.

This ensures that even if a user lies about the extension or the header, the server rejects any file whose internal structure doesn't match the allowed types.

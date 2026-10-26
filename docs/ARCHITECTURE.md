# Architecture

## Runtime flow

```text
Browser (Next.js App Router)
  ├─ Supabase Auth SSR / PKCE cookies for identity
  ├─ same-origin /api/v1/* → Next rewrite → FastAPI
  │    ├─ validates Supabase JWT with JWKS
  │    ├─ loads profile and checks role/membership on every subject route
  │    ├─ Neon PostgreSQL via SQLAlchemy / Alembic
  │    ├─ Cloudinary server SDK for private file storage
  │    └─ Gemini server SDK for grounded answers, MCQ, opt-in audio, study tools
  └─ no service-role key, database URL, Gemini key, or Cloudinary secret in client code
```

## Ownership boundaries

- Supabase owns authentication identities and sessions. Neon owns application profiles, subjects, memberships, content metadata, study sessions, quizzes, progress, YouTube links, transcripts, and cached artifacts.
- A new verified Supabase user receives a student profile. Client requests cannot set their role. Admin-only subject mutations depend on the Neon profile role.
- Resource reads and generation first verify membership, then constrain retrieval by subject ID. Gemini receives only selected passages from that subject. Documents are untrusted input.
- Cloudinary credentials remain server-side. Stored resources are private and exposed through short-lived signed delivery URLs.
- Gemini is called only by the backend. Audio is sent only after a user explicitly checks the per-upload consent box. Video URLs are parsed/embedded from the allowlist; the service does not fetch them.
- Generated artifacts are keyed on kind, model, prompt version, resource/page/chunk identity, and excerpt content. A uniqueness constraint prevents duplicate saved output for the same source set.

## API routing and CORS

`frontend/next.config.ts` rewrites `/api/v1/:path*` to `API_PROXY_TARGET`, defaulting to `http://127.0.0.1:8000`. Browser API requests are same-origin. Deployments can set `API_PROXY_TARGET` to the private API service URL. FastAPI still keeps a narrow `CORS_ORIGINS` allowlist for direct clients; it is not globally open. Next development allows only the confirmed WARP host `172.16.0.2` via `allowedDevOrigins`.

## Database evolution

- Two Alembic histories are retained: legacy `18a7e42bc901` and app-compatible branch `neon_existing_schema`.
- For the current app branch, use `alembic upgrade neon_existing_schema@head`; do not use ambiguous `alembic upgrade head`.
- `0011_study_artifacts` was tested on SQLite and a temporary Neon branch, then applied to the Neon branch named `production` with user approval. It adds one table and one index; no existing rows were removed or rewritten.
- Future destructive migrations or production data changes require explicit user approval and a tested migration branch.

## Current scope boundaries

Implemented flows include authentication, protected subject routes, study timers, private file upload/metadata, document extraction and BM25 retrieval, Gemini study assistance and MCQ, saved quiz attempts, progress API/dashboard, YouTube link embedding, opt-in audio transcript, and cached flashcards/concept maps/notes. Not yet implemented: OCR, vector embeddings, persistent chat threads, adaptive review recommendations, short-answer grading, admin role bootstrap, and end-to-end user browser tests.


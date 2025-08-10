-- Textpress hosted MVP database schema
-- Create the minimal table used by the backend to store rendered documents.

CREATE TABLE IF NOT EXISTS public.documents (
  id           text PRIMARY KEY,
  status       text NOT NULL DEFAULT 'published',
  created_at   timestamptz NOT NULL DEFAULT now(),
  source_type  text,
  input_name   text,
  html_body    text NOT NULL,
  md_body      text,
  parent_doc_id text,
  doc_metadata jsonb
);

-- Helpful index for recent listings (future use)
CREATE INDEX IF NOT EXISTS documents_created_at_idx ON public.documents (created_at DESC);

-- Index for finding child documents
CREATE INDEX IF NOT EXISTS documents_parent_doc_id_idx ON public.documents (parent_doc_id);



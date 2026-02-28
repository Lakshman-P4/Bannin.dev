-- Add tsvector column for full-text search on Event table
ALTER TABLE "Event" ADD COLUMN IF NOT EXISTS "search_vector" tsvector;

-- Populate existing rows
UPDATE "Event" SET "search_vector" = to_tsvector('english', coalesce("message", '') || ' ' || coalesce("type", '') || ' ' || coalesce("source", ''));

-- Create GIN index for fast search
CREATE INDEX IF NOT EXISTS "Event_search_vector_idx" ON "Event" USING GIN ("search_vector");

-- Auto-update trigger on insert/update
CREATE OR REPLACE FUNCTION event_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW."search_vector" := to_tsvector('english', coalesce(NEW."message", '') || ' ' || coalesce(NEW."type", '') || ' ' || coalesce(NEW."source", ''));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS event_search_vector_trigger ON "Event";
CREATE TRIGGER event_search_vector_trigger
  BEFORE INSERT OR UPDATE ON "Event"
  FOR EACH ROW EXECUTE FUNCTION event_search_vector_update();

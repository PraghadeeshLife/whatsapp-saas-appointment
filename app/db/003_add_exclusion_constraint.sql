-- 1. Enable the extension required for GIST exclusion constraints on standard types
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Add an exclusion constraint to prevent overlapping appointments
-- This ensures that for a given resource_id, no two appointments (confirmed/pending) 
-- can have overlapping time ranges.
ALTER TABLE appointments
ADD CONSTRAINT appointments_no_overlap
EXCLUDE USING GIST (
  resource_id WITH =,
  tstzrange(start_time, end_time) WITH &&
)
WHERE (status IN ('confirmed', 'pending'));

-- NOTE: If a user tries to book a slot that overlaps with an existing 
-- 'confirmed' or valid 'pending' record, Postgres will reject the INSERT 
-- with a '42P10' (or similar) error, keeping the system 100% consistent.

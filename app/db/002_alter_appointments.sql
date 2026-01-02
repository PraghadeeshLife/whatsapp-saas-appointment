-- 1. Add new columns
ALTER TABLE appointments 
ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS google_event_id TEXT;

-- 2. Update status column to include new states (if not using ENUM, just ensure code handles it)
-- If status was constrained, we might need to drop constraint. 
-- Existing default is 'scheduled'. We will use 'pending', 'confirmed', 'cancelled'.
ALTER TABLE appointments 
ALTER COLUMN status SET DEFAULT 'pending';

-- 3. Ensure start_time/appointment_time consistency
-- The existing table has `appointment_time` (TIMESTAMP WITH TIME ZONE).
-- We can alias this in our code as start_time or rename it. 
-- For clarity, let's rename `appointment_time` to `start_time` if preferred, or just use appointment_time.
-- Let's rename for consistency with our plan.
ALTER TABLE appointments 
RENAME COLUMN appointment_time TO start_time;

-- 4. Constraint for end_time (optional but good practice)
-- If we have existing rows without end_time, this might fail unless nullable.
-- We left it nullable in ADD COLUMN above.
-- For new code, we should enforce it.

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_appointments_status_expires ON appointments(status, expires_at);

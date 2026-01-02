-- Create ENUM for appointment status
CREATE TYPE appointment_status AS ENUM ('pending', 'confirmed', 'cancelled');

-- Create appointments table
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id BIGINT NOT NULL, -- Assumes a tenants table exists and ID is bigint
    resource_id TEXT NOT NULL,
    customer_name TEXT,
    customer_phone TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status appointment_status NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMPTZ, -- For pending reservations
    google_event_id TEXT, -- ID of the synced Google Calendar event
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes for faster availability queries
    CONSTRAINT appointments_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE INDEX idx_appointments_tenant_resource_time ON appointments(tenant_id, resource_id, start_time, end_time);
CREATE INDEX idx_appointments_status ON appointments(status);

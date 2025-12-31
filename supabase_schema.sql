CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL, -- Link to Supabase Auth (auth.users)
    name VARCHAR(255),
    whatsapp_phone_number_id VARCHAR(255) UNIQUE NOT NULL,
    whatsapp_access_token TEXT NOT NULL,
    webhook_verify_token VARCHAR(255),
    google_service_account_json TEXT, -- Service account JSON content
    google_calendar_id VARCHAR(255),  -- The clinic's calendar ID (usually an email)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Appointments Table
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    customer_name VARCHAR(255),
    customer_phone VARCHAR(255) NOT NULL,
    appointment_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Messages Table (Tracking Inbound/Outbound)
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    sender_number VARCHAR(255) NOT NULL,
    recipient_number VARCHAR(255) NOT NULL,
    text TEXT,
    direction VARCHAR(10) CHECK (direction IN ('inbound', 'outbound')),
    status VARCHAR(50), -- e.g., 'received', 'sent', 'delivered', 'read'
    whatsapp_message_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Resources Table (Generic: Doctors, Rooms, etc.)
CREATE TABLE IF NOT EXISTS resources (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT, -- e.g., Specialty or Room Type
    external_id VARCHAR(255), -- ID in external system (like Google Calendar)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Update Appointments Table to reference resources
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS resource_id INTEGER REFERENCES resources(id) ON DELETE SET NULL;

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_tenants_phone_id ON tenants(whatsapp_phone_number_id);
CREATE INDEX IF NOT EXISTS idx_appointments_customer_phone ON appointments(customer_phone);
CREATE INDEX IF NOT EXISTS idx_messages_tenant_id ON messages(tenant_id);
CREATE INDEX IF NOT EXISTS idx_messages_whatsapp_id ON messages(whatsapp_message_id);
CREATE INDEX IF NOT EXISTS idx_resources_tenant_id ON resources(tenant_id);

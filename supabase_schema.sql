-- Create Tenants Table
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    whatsapp_phone_number_id VARCHAR(255) UNIQUE NOT NULL,
    whatsapp_access_token TEXT NOT NULL,
    webhook_verify_token VARCHAR(255),
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

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_tenants_phone_id ON tenants(whatsapp_phone_number_id);
CREATE INDEX IF NOT EXISTS idx_appointments_customer_phone ON appointments(customer_phone);
CREATE INDEX IF NOT EXISTS idx_messages_tenant_id ON messages(tenant_id);
CREATE INDEX IF NOT EXISTS idx_messages_whatsapp_id ON messages(whatsapp_message_id);

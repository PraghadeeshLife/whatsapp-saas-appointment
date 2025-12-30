from app.db.session import engine
from app.db.base_class import Base
from app.models.tenant import Tenant
from app.models.appointment import Appointment

def init_db():
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()

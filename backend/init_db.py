from app.database.connection import Base, engine
from app.models.user import User


print("Creating database tables...")

Base.metadata.create_all(bind=engine)

print("Database created successfully!")
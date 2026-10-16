from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base
import uuid

class Church(Base):
    __tablename__ = "churches"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    # A permanent, unique string to generate the QR code
    qr_code_hash = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    rooms = relationship("Room", back_populates="church")

class Room(Base):
    __tablename__ = "rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"))
    is_live = Column(Boolean, default=False)
    
    church = relationship("Church", back_populates="rooms")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True) # Nullable for guests
    hashed_password = Column(String, nullable=True)
    is_guest = Column(Boolean, default=True)
    church_id = Column(Integer, ForeignKey("churches.id"), nullable=True)

    church = relationship("Church")
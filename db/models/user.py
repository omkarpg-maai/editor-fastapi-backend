from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'User'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    displayname = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    tagTree = Column(JSON, default={})
    sl_id = Column(String(36), nullable=False, unique=True)
    external_id = Column(String(36), nullable=False, unique=True)
    provider = Column(String, default='SUPABASE')
    grant_id = Column(Text)
    bot_config = Column(JSON, default={"bot_name": "Supaloops.app"})
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    timezone = Column(Text)

    # Define relationship to UserMeetings
    meetings = relationship("UserMeetings", back_populates="user")

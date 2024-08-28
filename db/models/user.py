from sqlalchemy import Column, Integer, Text, JSON, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from db.sessions import Base

class User(Base):
    __tablename__ = 'User'
    
    id = Column(Integer, primary_key=True, index=True)
    displayname = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    tagTree = Column(JSONB, nullable=False, default={})
    sl_id = Column(String(36), nullable=False, unique=True)
    external_id = Column(String(36), nullable=False, unique=True)
    provider = Column(ENUM('SUPABASE', 'GOOGLE', 'GITHUB', name='AuthenticationProvider'), nullable=False, default='SUPABASE')
    grant_id = Column(Text)
    bot_config = Column(JSONB, nullable=False, default={"bot_name": "Supaloops.app"})
    createdAt = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    timezone = Column(Text)

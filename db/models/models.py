from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    ForeignKey,
    Boolean,
    Enum,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


# Enum for MeetingBotStatus
class MeetingBotStatus(enum.Enum):
    NOT_ADDED = "NOT_ADDED"
    # Add other statuses if needed


# User Model
class User(Base):
    __tablename__ = "User"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    displayname = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    tagTree = Column(JSON, default={})
    sl_id = Column(String(36), nullable=False, unique=True)
    external_id = Column(String(36), nullable=False, unique=True)
    provider = Column(String, default="SUPABASE")
    grant_id = Column(Text)
    bot_config = Column(JSON, default={"bot_name": "Supaloops.app"})
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    timezone = Column(Text)

    # Define relationship to UserMeetings
    meetings = relationship("UserMeetings", back_populates="user")


# UserMeetings Model
class UserMeetings(Base):
    __tablename__ = "UserMeetings_python"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(
        Integer,
        ForeignKey("public.User.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    documentId = Column(
        String(36),
        ForeignKey("public.Document.id", ondelete="SET NULL", onupdate="CASCADE"),
    )
    calendar_uid = Column(Text, nullable=False)
    master_cal_uid = Column(Text)
    event_url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    participants = Column(Text, nullable=False)
    organizer = Column(Integer)
    start_time = Column(Integer, nullable=False)
    timezone = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    disable_bot = Column(Boolean, nullable=False, default=False)
    type = Column(Text, nullable=False, default="one_time")
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    start_date = Column(Date, nullable=False)
    end_time = Column(Integer)
    uniq_identifier = Column(Text)
    Agenda = Column(Text)
    bot_id = Column(Text)
    rough_notes = Column(JSON)
    bot_status = Column(
        Enum(MeetingBotStatus), nullable=False, default=MeetingBotStatus.NOT_ADDED
    )

    # Define relationship to User
    user = relationship("User", back_populates="meetings")

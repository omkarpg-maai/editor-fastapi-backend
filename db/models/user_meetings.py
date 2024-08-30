from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, ForeignKey, Enum, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Sequence
import enum
from datetime import datetime


from db.sessions import Base

# Define Enum for MeetingBotStatus if it's used
class MeetingBotStatus(enum.Enum):
    NOT_ADDED = 'NOT_ADDED'
    # Add other possible values if needed

class UserMeetings(Base):
    __tablename__ = 'UserMeetings'
    __table_args__ = {'schema': 'public'}

    # Columns
    id = Column(Integer, Sequence('UserMeetings_id_seq'), primary_key=True)
    userId = Column(Integer, ForeignKey('public."User".id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    documentId = Column(String(36), ForeignKey('public."Document".id', ondelete='SET NULL', onupdate='CASCADE'))
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
    type = Column(Text, nullable=False, default='one_time')
    createdAt = Column(DateTime, nullable=False, default=datetime.utcnow)
    updatedAt = Column(DateTime, nullable=False)
    start_date = Column(Date, nullable=False)
    end_time = Column(Integer)
    uniq_identifier = Column(Text)
    Agenda = Column(Text)
    bot_id = Column(Text)
    rough_notes = Column(JSON)
    bot_status = Column(Enum(MeetingBotStatus), nullable=False, default=MeetingBotStatus.NOT_ADDED)

    # Relationships
    user = relationship('User', backref='user_meetings')
    document = relationship('Document', backref='user_meetings')

    # Constraints
    __table_args__ = (
        UniqueConstraint('userId', 'uniq_identifier', 'start_time', name='UserMeetings_userId_uniq_identifier_start_time_key'),
    )

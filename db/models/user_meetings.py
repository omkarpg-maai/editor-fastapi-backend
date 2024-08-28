from sqlalchemy import Column, Integer, Text, String, Boolean, Date, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from sqlalchemy.orm import relationship
from db.sessions import Base

 
class UserMeetings(Base):
    __tablename__ = 'UserMeetings'
    
    id = Column(Integer, primary_key=True, index=True)
    userId = Column(Integer, ForeignKey('User.id'), nullable=False)
    documentId = Column(String(36), ForeignKey('Document.id'))
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
    createdAt = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updatedAt = Column(DateTime(timezone=False), onupdate=func.now(), nullable=False)
    start_date = Column(Date, nullable=False)
    end_time = Column(Integer)
    uniq_identifier = Column(Text)
    Agenda = Column(Text)
    bot_id = Column(Text)
    rough_notes = Column(JSONB)
    bot_status = Column(ENUM('NOT_ADDED', 'ADDED', 'REMOVED', name='MeetingBotStatus'), nullable=False, default='NOT_ADDED')

    user = relationship("User", back_populates="meetings")

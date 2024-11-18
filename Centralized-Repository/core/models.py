from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Publication(Base):
    __tablename__ = 'publications'
    
    id = Column(Integer, primary_key=True)
    doi = Column(String, unique=True)
    title = Column(String)
    abstract = Column(String)
    source_system = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    authors = relationship("Author", secondary="publication_authors")

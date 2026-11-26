from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from saveclock.models.base import Base, TimestampMixin


class Song(TimestampMixin, Base):
    __tablename__ = "songs"
    __table_args__ = (
        UniqueConstraint("project_id"),
        CheckConstraint("size_bytes >= 0", name="size_bytes"),
        CheckConstraint("sha256 IS NULL OR octet_length(sha256) = 32", name="sha256_len"),
        Index("ix_songs_sha256", "sha256"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    duration_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    codec: Mapped[str | None] = mapped_column(Text)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(SmallInteger)
    sha256: Mapped[bytes | None] = mapped_column(LargeBinary)
    source_ext: Mapped[str | None] = mapped_column(Text)

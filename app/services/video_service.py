from sqlalchemy.orm import Session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status

from app.models.user import User
from app.models.channel import Channel
from app.models.video import Video, VideoVisibility
from app.models.video_public_id import VideoPublicId
from app.schemas.video import VideoUpdate
from app.services.authorization_service import AuthorizationService
from app.crud.video import video as video_crud



class VideoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthorizationService(db)

    async def update_video(
        self,
        db: Session,
        public_id: str,
        current_user: User,
        request: VideoUpdate
    ):
        # Get video obj
        video = await video_crud.get_by_public_id(self.db, public_id)

        if not self.auth_service.is_admin_or_channel_owner(current_user, video.channel):
            raise HTTPException(status=status.HTTP_403_FORBIDDEN)

        # Update in db
        return await video_crud.put_video(db=db, video_id=video.id, video=request)


async def get_video_by_public_id(
    db: AsyncSession,
    public_id: str,
    requesting_user_id: int | None,  # None = unauthenticated
) -> Video:
    video = await video_crud.get_by_public_id(db, public_id)

    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    # Visibility rules
    if video.visibility == VideoVisibility.PUBLIC:
        return video

    # Private and unlisted require the requester to be authenticated
    if requesting_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    if video.visibility == VideoVisibility.PRIVATE:
        if "channel" not in video.__dict__:
            await db.refresh(video, attribute_names=["channel"])
        # Fixed: Channel model uses `user_id`, not `owner_user_id`
        if video.channel.user_id != requesting_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Unlisted: any authenticated user with the link can access — no ownership check needed

    return video
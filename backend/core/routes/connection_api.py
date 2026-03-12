import logging
from ninja import Router
from core.schemas.schemas import ConnectionRequestSchema, ConnectionResponseSchema
from core.services.connection_service import ConnectionService

logger = logging.getLogger(__name__)
router = Router()


@router.post("/", response={200: dict, 400: dict})
def send_connection(request, payload: ConnectionRequestSchema):
    try:
        ConnectionService.send_request(request.user, payload.receiver_id)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Connection request error: {e}")
        return 400, {"detail": str(e)}


@router.get("/", response={200: list, 400: dict})
def get_connections(request):
    try:
        data = ConnectionService.get_connections(request.user)
        return data
    except Exception as e:
        logger.error(f"Get connections error: {e}")
        return 400, {"detail": str(e)}


@router.put("/{connection_id}", response={200: dict, 400: dict})
def respond_connection(request, connection_id: str, payload: ConnectionResponseSchema):
    try:
        ConnectionService.respond_to_request(request.user, connection_id, payload.accept)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Connection response error: {e}")
        return 400, {"detail": str(e)}
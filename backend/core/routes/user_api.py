from ninja import Router

router = Router()

@router.get("/")
def get_users(request):
    return {"status": "todo"}
import asyncio
from app.core.dependencies import get_graph_client, get_sync_service


async def main():
    sync_service = get_sync_service()
    token = await get_graph_client().get_application_token()
    result = await sync_service.sync_attendance(token=token)
    print(result)


asyncio.run(main())

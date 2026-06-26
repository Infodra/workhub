import asyncio, logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')
from app.core.dependencies import get_graph_client, get_sharepoint_repository

async def main():
    gc = get_graph_client()
    sp = get_sharepoint_repository()
    token = await gc.get_application_token()
    items = await sp.get_list_items(token, 'Attendance')
    jun26 = [i for i in items if (i.get('fields', {}).get('Date') or '').startswith('2026-06-26')]
    for item in jun26:
        f = item.get('fields', {})
        print(f.get('EmployeeEmail','?'), 'status:', f.get('Status','?'), 'hours:', f.get('WorkingHours','?'), 'remarks:', f.get('Remarks',''))

asyncio.run(main())
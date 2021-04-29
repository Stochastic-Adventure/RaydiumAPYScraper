import os
import aiohttp
import asyncio
from aiolimiter import AsyncLimiter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from LPInfo import RaydiumPoolInfo
from pprint import pprint

async def amain():
    limiter = AsyncLimiter(15, 1)

    task = []
    async with aiohttp.ClientSession() as session:
        async with limiter:
            LP = RaydiumPoolInfo(session)
            fee_apy_task = asyncio.create_task(LP.RAYDIUM.get_pair())
            fee_apy = await fee_apy_task

            for farm in LP.farms_info:
                task.append(LP.get_APR(farm))
            result = await asyncio.gather(*task)

            for farm in result:
                farm_name = list(farm.keys())[0]
                farm[farm_name].update({"Fee_APR": fee_apy[farm_name]})
                pprint(farm)

if __name__ == '__main__':
    scheduler = AsyncIOScheduler()
    scheduler.add_job(amain, 'cron', minute='*')
    scheduler.start()
    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    # Execution will block here until Ctrl+C (Ctrl+Break on Windows) is pressed.
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
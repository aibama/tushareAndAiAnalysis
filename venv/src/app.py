

from datetime import datetime
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from crawling.SinaStockCompose import SinaStockCompose

try:
    import asyncio
except ImportError:
    import trollius as asyncio



if __name__ == '__main__':
    scheduler = AsyncIOScheduler()
    sinastock = SinaStockCompose()
    scheduler.add_job(sinastock.docrawStockComposition(), 'interval', hour=5)
    scheduler.start()

    # Execution will block here until Ctrl+C (Ctrl+Break on Windows) is pressed.
    try:
        asyncio.get_event_loop().run_forever()
    except (SystemExit):
        pass
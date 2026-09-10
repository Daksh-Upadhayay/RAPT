from fastapi import FastAPI

from app.routers import knowledge_base, orders, tickets

app = FastAPI(title="RAPT Backend")

app.include_router(tickets.router)
app.include_router(orders.router)
app.include_router(knowledge_base.router)

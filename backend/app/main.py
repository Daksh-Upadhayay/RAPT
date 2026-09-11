from fastapi import FastAPI

from app.routers import agents, knowledge_base, orders, reviews, tickets

app = FastAPI(title="RAPT Backend")

app.include_router(tickets.router)
app.include_router(orders.router)
app.include_router(knowledge_base.router)
app.include_router(agents.router)
app.include_router(reviews.router)

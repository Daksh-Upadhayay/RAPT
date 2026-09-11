from fastapi import FastAPI

from app.routers import agents, customers, knowledge_base, metrics, orders, reviews, tickets

app = FastAPI(title="RAPT Backend")

app.include_router(tickets.router)
app.include_router(orders.router)
app.include_router(customers.router)
app.include_router(knowledge_base.router)
app.include_router(agents.router)
app.include_router(reviews.router)
app.include_router(metrics.router)

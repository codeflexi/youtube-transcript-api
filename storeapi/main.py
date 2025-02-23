from enum import Enum

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello , tuk tuk tuk"}


# @app.get("/items/all")
# async def get_all_items():
#     return {"items": "all items"}


# Query Parameters
@app.get("/items/all")
async def get_all_items(page: int = 1, limit: int = 10):
    return {"Pages": f"page is {page} and limit is {limit}"}


class ItemType(str, Enum):
    rawmaterial = "rawmaterial"
    semifinished = "semifinished"
    finished = "finished"


# Path Parameter
@app.get("/items/type/{type}")
async def get_item_type(type: ItemType):
    return {"item_type": f"Item Type is :{type}"}


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    return {"item_id": item_id}

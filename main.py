import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Order, OrderItem, Customer

app = FastAPI(title="Sepatuku API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers

def to_str_id(doc):
    if not doc:
        return doc
    if isinstance(doc, list):
        return [to_str_id(d) for d in doc]
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d["_id"])  # expose as id
        del d["_id"]
    return d


# Seed products if empty
@app.on_event("startup")
async def seed_products():
    try:
        if db is None:
            return
        count = db["product"].count_documents({})
        if count == 0:
            seed = [
                {
                    "title": "Sepatuku Runner Pro",
                    "description": "Sepatu lari ringan dengan bantalan empuk.",
                    "price": 499000,
                    "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Running",
                    "in_stock": True,
                },
                {
                    "title": "Sepatuku Street Classic",
                    "description": "Gaya kasual untuk sehari-hari.",
                    "price": 399000,
                    "image": "https://images.unsplash.com/photo-1519741497674-611481863552?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Casual",
                    "in_stock": True,
                },
                {
                    "title": "Sepatuku Court Ace",
                    "description": "Sneakers putih bersih serbaguna.",
                    "price": 459000,
                    "image": "https://images.unsplash.com/photo-1543508282-6319a3e2621f?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Sneakers",
                    "in_stock": True,
                },
            ]
            for s in seed:
                create_document("product", s)
    except Exception:
        pass


# Routes
@app.get("/")
def root():
    return {"message": "Sepatuku API Running"}

@app.get("/products")
def list_products():
    docs = get_documents("product")
    return to_str_id(docs)

class CartItem(BaseModel):
    product_id: str
    quantity: int

class CheckoutRequest(BaseModel):
    items: List[CartItem]
    customer: Customer
    payment_method: str

@app.post("/checkout")
def checkout(payload: CheckoutRequest):
    # Validate products and compute total
    total = 0
    order_items: List[OrderItem] = []
    for item in payload.items:
        try:
            prod = db["product"].find_one({"_id": ObjectId(item.product_id)})
        except Exception:
            prod = None
        if not prod:
            raise HTTPException(status_code=400, detail=f"Produk tidak ditemukan: {item.product_id}")
        if not prod.get("in_stock", True):
            raise HTTPException(status_code=400, detail=f"Produk sedang habis: {prod.get('title')}")
        price = float(prod.get("price", 0))
        total += price * item.quantity
        order_items.append(OrderItem(
            product_id=str(prod["_id"]),
            title=prod.get("title"),
            price=price,
            quantity=item.quantity,
            image=prod.get("image")
        ))

    pm = payload.payment_method.upper()
    if pm not in ["COD", "QRIS"]:
        raise HTTPException(status_code=400, detail="Metode pembayaran tidak didukung")

    order = Order(
        items=order_items,
        total=total,
        payment_method=pm, 
        status="pending" if pm == "QRIS" else "cod-confirmed",
        customer=payload.customer
    )

    order_id = create_document("order", order)

    response = {
        "order_id": order_id,
        "total": total,
        "payment_method": pm,
        "status": order.status,
    }

    if pm == "QRIS":
        # For demo, return a placeholder QR code image URL encoding order id + total
        # In real case, integrate with QRIS provider to get dynamic QR string
        import urllib.parse
        qr_text = f"SEPATUKU|ORDER:{order_id}|TOTAL:{int(total)}"
        encoded = urllib.parse.quote(qr_text)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={encoded}"
        response["qris_qr_url"] = qr_url
        response["instructions"] = "Scan QRIS untuk menyelesaikan pembayaran."
    else:
        response["instructions"] = "Pesanan COD dikonfirmasi. Siapkan pembayaran tunai saat kurir datang."

    return response

@app.get("/orders")
def list_orders():
    docs = get_documents("order")
    return to_str_id(docs)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

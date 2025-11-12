import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Union
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Order, OrderItem, Customer, SizeStock

app = FastAPI(title="Sepatuku API", version="1.1.0")

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


def fix_image_urls(p):
    # Correct wrong photo for Street Classic and ensure https & parameters ok
    title = p.get("title", "").lower()
    if "street classic" in title:
        p["image"] = "https://images.unsplash.com/photo-1519741495605-1f7f1c080b42?w=800&q=80&auto=format&fit=crop"
    return p


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
                    "sizes": [
                        {"size": 40, "stock": 10},
                        {"size": 41, "stock": 12},
                        {"size": 42, "stock": 8},
                    ],
                },
                {
                    "title": "Sepatuku Street Classic",
                    "description": "Gaya kasual untuk sehari-hari.",
                    "price": 399000,
                    "image": "https://images.unsplash.com/photo-1519741495605-1f7f1c080b42?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Casual",
                    "in_stock": True,
                    "sizes": [
                        {"size": 39, "stock": 6},
                        {"size": 40, "stock": 10},
                        {"size": 41, "stock": 10},
                    ],
                },
                {
                    "title": "Sepatuku Court Ace",
                    "description": "Sneakers putih bersih serbaguna.",
                    "price": 459000,
                    "image": "https://images.unsplash.com/photo-1543508282-6319a3e2621f?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Sneakers",
                    "in_stock": True,
                    "sizes": [
                        {"size": 40, "stock": 7},
                        {"size": 41, "stock": 7},
                        {"size": 42, "stock": 5},
                    ],
                },
                # Extra catalog
                {
                    "title": "Sepatuku Trail Grip",
                    "description": "Traksi maksimal untuk medan berat.",
                    "price": 529000,
                    "image": "https://images.unsplash.com/photo-1539185441755-769473a23570?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Outdoor",
                    "in_stock": True,
                    "sizes": [
                        {"size": 40, "stock": 5},
                        {"size": 41, "stock": 9},
                        {"size": 42, "stock": 4},
                    ],
                },
                {
                    "title": "Sepatuku AirFlex",
                    "description": "Ringan, fleksibel, nyaman sepanjang hari.",
                    "price": 379000,
                    "image": "https://images.unsplash.com/photo-1600180758890-6b94519a8ba6?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Lifestyle",
                    "in_stock": True,
                    "sizes": [
                        {"size": 39, "stock": 11},
                        {"size": 40, "stock": 13},
                        {"size": 41, "stock": 9},
                    ],
                },
                {
                    "title": "Sepatuku Retro Runner",
                    "description": "Nuansa retro dengan teknologi masa kini.",
                    "price": 449000,
                    "image": "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=800&q=80&auto=format&fit=crop",
                    "brand": "Sepatuku",
                    "category": "Running",
                    "in_stock": True,
                    "sizes": [
                        {"size": 40, "stock": 6},
                        {"size": 41, "stock": 6},
                        {"size": 42, "stock": 6},
                    ],
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
def list_products(q: Optional[str] = Query(None), category: Optional[str] = Query(None)):
    query = {}
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"brand": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]
    if category:
        query["category"] = {"$regex": f"^{category}$", "$options": "i"}

    docs = list(db["product"].find(query))
    docs = [fix_image_urls(d) for d in docs]
    return to_str_id(docs)

class CartItem(BaseModel):
    product_id: str
    quantity: int
    size: Union[str, int]

class CheckoutRequest(BaseModel):
    items: List[CartItem]
    customer: Customer
    payment_method: str

@app.post("/checkout")
def checkout(payload: CheckoutRequest):
    # Validate products, sizes, and compute total, decrease stock
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

        # Validate size availability
        sizes = prod.get("sizes", [])
        size_entry = next((s for s in sizes if str(s.get("size")) == str(item.size)), None)
        if not size_entry or size_entry.get("stock", 0) < item.quantity:
            raise HTTPException(status_code=400, detail=f"Stok ukuran {item.size} tidak mencukupi untuk {prod.get('title')}")

        price = float(prod.get("price", 0))
        total += price * item.quantity
        order_items.append(OrderItem(
            product_id=str(prod["_id"]),
            title=prod.get("title"),
            price=price,
            quantity=item.quantity,
            image=prod.get("image"),
            size=item.size,
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

    # Reduce stock per size atomically (best effort per item)
    for oi in order_items:
        db["product"].update_one(
            {"_id": ObjectId(oi.product_id), "sizes.size": oi.size},
            {"$inc": {"sizes.$.stock": -oi.quantity}}
        )
        # Update in_stock flag if all sizes depleted
        prod = db["product"].find_one({"_id": ObjectId(oi.product_id)})
        if prod:
            sizes = prod.get("sizes", [])
            if all((s.get("stock", 0) <= 0) for s in sizes):
                db["product"].update_one({"_id": ObjectId(oi.product_id)}, {"$set": {"in_stock": False}})

    response = {
        "order_id": order_id,
        "total": total,
        "payment_method": pm,
        "status": order.status,
    }

    if pm == "QRIS":
        # For demo, return a placeholder QR code image URL encoding order id + total
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

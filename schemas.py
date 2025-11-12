"""
Database Schemas for Sepatuku

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in IDR")
    image: Optional[str] = Field(None, description="Image URL")
    brand: Optional[str] = Field("Sepatuku", description="Brand name")
    category: Optional[str] = Field("Shoes", description="Category")
    in_stock: bool = Field(True, description="Stock availability")

class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = Field(ge=1)
    image: Optional[str] = None

class Customer(BaseModel):
    name: str
    email: str
    phone: str
    address: str
    city: Optional[str] = None
    postal_code: Optional[str] = None

class Order(BaseModel):
    items: List[OrderItem]
    total: float = Field(ge=0)
    payment_method: Literal["COD", "QRIS"]
    status: Literal["pending", "paid", "cod-confirmed"] = "pending"
    customer: Customer

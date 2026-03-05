from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum


class Status(str, Enum):
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ShippingType(str, Enum):
    DAYS_1_7 = "1_7_days"
    DAYS_15_20 = "15_20_days"
    DAYS_20_30 = "20_30_days"


class ShipmentBase(BaseModel):
    title: str = ""
    tracking: str = ""
    product_list: str = ""
    notes: str = ""
    dispatch_date: date
    delivery_date: Optional[date] = None
    status: Status = Status.IN_TRANSIT
    shipping_type: ShippingType
    weight: float = 0
    amount_to_pay: float = 0
    cashback: float = 0
    calculated: bool = False
    client_id: Optional[str] = None
    client_phone: Optional[str] = None


class ShipmentCreate(ShipmentBase):
    pass


class ShipmentUpdate(BaseModel):
    title: Optional[str] = None
    tracking: Optional[str] = None
    product_list: Optional[str] = None
    notes: Optional[str] = None
    dispatch_date: Optional[date] = None
    delivery_date: Optional[date] = None
    status: Optional[Status] = None
    shipping_type: Optional[ShippingType] = None
    weight: Optional[float] = None
    amount_to_pay: Optional[float] = None
    cashback: Optional[float] = None
    calculated: Optional[bool] = None
    client_id: Optional[str] = None
    client_phone: Optional[str] = None


class ShipmentResponse(ShipmentBase):
    id: str
    file1: Optional[str] = None
    file2: Optional[str] = None
    file3: Optional[str] = None
    created_at: datetime
    client_id: Optional[str] = None
    client_phone: Optional[str] = None
    client_name: Optional[str] = None  # ФИО из справочника клиентов (ТГ), для отображения в таблице

    class Config:
        from_attributes = True


class ClientCreate(BaseModel):
    full_name: str = ""
    city: str = ""
    telegram_chat_id: Optional[str] = None
    phone: Optional[str] = None


class ClientUpdate(BaseModel):
    full_name: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None


class ClientResponse(BaseModel):
    id: str
    full_name: str
    city: str
    telegram_chat_id: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

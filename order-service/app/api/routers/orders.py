import uuid
from decimal import Decimal

from fastapi import APIRouter, status

from app.core.security import CurrentUserDep
from app.schemas.command import CreateOrderCommand
from app.schemas.request import OrderCreateRequestDTO
from app.schemas.response import CreateOrderResponseDTO, OrderResponseDTO
from app.services.order import OrderServiceDependency

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "", response_model=CreateOrderResponseDTO, status_code=status.HTTP_201_CREATED
)
async def create_order(
    dto: OrderCreateRequestDTO,
    current_user: CurrentUserDep,
    service: OrderServiceDependency,
) -> CreateOrderResponseDTO:
    # Compute total_amount from items
    total_amount = sum(item.unit_price * item.quantity for item in dto.items)

    items_payload = [item.model_dump(mode="json") for item in dto.items]

    order = await service.create_order(
        cmd=CreateOrderCommand(
            user_id=current_user.user_id,
            items=items_payload,
            total_amount=Decimal(str(total_amount)),
            currency=dto.currency,
        )
    )
    return CreateOrderResponseDTO.model_validate(order, from_attributes=True)


@router.get("", response_model=list[OrderResponseDTO])
async def list_orders(
    current_user: CurrentUserDep,
    service: OrderServiceDependency,
) -> list[OrderResponseDTO]:
    orders = await service.get_orders(current_user=current_user)
    return [OrderResponseDTO.model_validate(o, from_attributes=True) for o in orders]


@router.get("/{order_id}", response_model=OrderResponseDTO)
async def get_order(
    order_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: OrderServiceDependency,
) -> OrderResponseDTO:
    order = await service.get_order(order_id=order_id, current_user=current_user)
    return OrderResponseDTO.model_validate(order, from_attributes=True)


@router.patch("/{order_id}/cancel", response_model=OrderResponseDTO)
async def cancel_order(
    order_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: OrderServiceDependency,
) -> OrderResponseDTO:
    order = await service.cancel_order(order_id=order_id, current_user=current_user)
    return OrderResponseDTO.model_validate(order, from_attributes=True)

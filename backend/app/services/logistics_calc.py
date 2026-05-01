"""
Logistics & margin calculator for WB products.

Formulas:
  Delivery per shipment = (first_liter + (volume-1) * extra_liter * KTR + price * IRP/100)
  Every order gets delivered -> delivery_total = delivery_per_shipment * order_count
  
  Return logistics = 143 rub per return
  Expected returns = orders * (1 - bp)  OR  (orders - buyouts) if buyouts known
  return_total = 143 * expected_returns
  
  Total logistics = delivery_total + return_total
  
  Per-buyout logistics cost (for pricing) = total_logistics / buyout_count
    which equals: (base + price*IRP)/bp + (1/bp - 1)*143  [the original formula]
"""


def calc_volume_liters(width_cm: float, height_cm: float, length_cm: float) -> float:
    return (width_cm * height_cm * length_cm) / 1000


def calc_delivery_per_shipment(volume_liters: float, first_liter_rate: float,
                                extra_liter_rate: float, ktr: float,
                                price: float, irp: float) -> float:
    """
    Cost of one delivery (to client).
    Formula: (FL + EL * (vol - 1)) * IL + price * IRP / 100
    
    FL, EL come from warehouse_tariffs (already include warehouse coefficient).
    ktr = index of localization (IL), e.g. 1.07
    irp = index of sales distribution (IRP), e.g. 1.77 (percent)
    """
    if volume_liters <= 1:
        base = first_liter_rate
    else:
        base = first_liter_rate + extra_liter_rate * (volume_liters - 1)
    irp_pct = irp / 100 if irp > 1 else irp
    return round(base * ktr + price * irp_pct, 2)

def calc_return_per_shipment() -> float:
    """Cost of one return shipment. Fixed 143 rub."""
    return 143.0


def calc_logistics_per_buyout(volume_liters: float, first_liter_rate: float,
                               extra_liter_rate: float, ktr: float,
                               price: float, irp: float, buyout_pct_frac: float) -> float:
    """Total logistics cost allocated per 1 buyout (for pricing calculator)."""
    bp = max(buyout_pct_frac, 0.01)
    delivery = calc_delivery_per_shipment(volume_liters, first_liter_rate, extra_liter_rate, ktr, price, irp)
    # Per buyout: delivery/bp + return*(1/bp-1) = (delivery + 143*(1-bp)) / bp
    return round((delivery + 143 * (1 - bp)) / bp, 2)


def calc_storage_per_day(volume_liters: float, warehouse_coef: float = 1.0) -> float:
    if volume_liters <= 1:
        return round(0.08 * volume_liters, 4)
    return round((0.08 + 0.08 * (volume_liters - 1)) * warehouse_coef, 4)


def calc_metrics(
    order_count: int = 0,
    order_sum: float = 0,
    buyout_count: int = 0,
    buyout_sum: float = 0,
    buyout_percent: float = 0,
    returns_count: int = 0,
    cost_price: float = 0,
    volume_liters: float = 0,
    first_liter_rate: float = 73.6,
    extra_liter_rate: float = 22.4,
    warehouse_coef: float = 1.0,
    ktr: float = 1.07,
    irp: float = 1.77,
    commission_pct: float = 3.5,
    seller_coef: float = 0.647,
    acquiring_pct: float = 2.6,
    ad_spend: float = 0,
    tax_rate: float = 0,
    vat_rate: float = 0,
    avg_price_before_spp: float = 0,
    stock_quantity: int = 0,
    storage_days: int = 1,
    logistics_multiplier: float = 1.85,
    **kwargs
) -> dict:
    empty = {
        "delivery_cost": 0, "return_cost": 0, "logistics_total_per_order": 0,
        "storage_cost": 0, "commission_amount": 0, "commission_pct": 0,
        "cost_price_total": 0, "margin_profit": 0, "margin_profit_pct": 0,
        "margin_clean": 0, "margin_clean_pct": 0, "roi": 0, "profit_per_buyout": 0,
    }
    if order_count <= 0:
        return empty

    # --- Buyout percent as fraction ---
    bp = buyout_percent / 100 if buyout_percent > 1 else buyout_percent
    bp = max(bp, 0.01)

    # --- Price ---
    price = avg_price_before_spp or (order_sum / order_count if order_count > 0 else 0)

    # --- Delivery: every order gets shipped ---
    delivery_per_shipment = calc_delivery_per_shipment(
        volume_liters, first_liter_rate, extra_liter_rate, ktr, price, irp
    )
    delivery_total = round(delivery_per_shipment * order_count, 2)

    # --- Returns: each non-buyout gets returned ---
    expected_returns = round(order_count * (1 - bp))
    return_total = round(143.0 * expected_returns, 2)

    # Apply correction multiplier (inter-warehouse transfers, rebill, etc.)
    delivery_total = round(delivery_total * logistics_multiplier, 2)
    return_total = round(return_total * logistics_multiplier, 2)
    logistics_total = delivery_total + return_total

    # --- Per-order values (for storage in DB) ---
    delivery_cost_per_order = delivery_per_shipment
    return_cost_per_order = round(143.0 * (1 - bp), 2)

    # --- Storage ---
    storage_per_day = calc_storage_per_day(volume_liters, warehouse_coef)
    storage_cost = round(storage_per_day * stock_quantity * storage_days, 2)

    # --- Payout (seller_coef includes WB discount + commission + acquiring) ---
    payout_sales = round(buyout_sum * seller_coef, 2)
    
    # Returns payout (estimated)
    avg_buyout_price = buyout_sum / buyout_count if buyout_count > 0 else (order_sum / order_count if order_count > 0 else 0)
    payout_returns = round(expected_returns * avg_buyout_price * seller_coef, 2)

    # --- Commission (for display only) ---
    commission_amount = round(buyout_sum * commission_pct / 100, 2)

    # --- Cost price ---
    net_qty = max(buyout_count - returns_count, 0)
    cost_price_total = round(cost_price * net_qty, 2)

    # --- Payout returns (WB claws back payout for returned items) ---
    # Use actual returns_count if available, otherwise estimate from bp
    actual_returns = returns_count  # only use actual returns, no estimation
    payout_returns = round(actual_returns * avg_buyout_price * seller_coef, 2)
    
    # --- Net payout ---
    net_payout = round(payout_sales - payout_returns - logistics_total - storage_cost, 2)

    # --- Margin ---
    margin_profit = round(net_payout - cost_price_total, 2)
    margin_profit_pct = round(margin_profit / buyout_sum * 100, 2) if buyout_sum > 0 else 0

    # --- Clean margin ---
    tax_amount = round(max(margin_profit, 0) * tax_rate / 100, 2) if tax_rate > 0 else 0
    margin_clean = round(margin_profit - ad_spend - tax_amount, 2)
    margin_clean_pct = round(margin_clean / buyout_sum * 100, 2) if buyout_sum > 0 else 0

    # --- ROI ---
    total_investment = cost_price_total + ad_spend + logistics_total + storage_cost
    roi = round(margin_clean / total_investment * 100, 2) if total_investment > 0 else 0

    # --- Profit per buyout ---
    profit_per_buyout = round(margin_clean / buyout_count, 2) if buyout_count > 0 else 0

    return {
        "delivery_cost": round(delivery_cost_per_order, 2),
        "return_cost": round(return_cost_per_order, 2),
        "logistics_total_per_order": round(logistics_total / order_count, 2) if order_count > 0 else 0,
        "storage_cost": storage_cost,
        "commission_amount": commission_amount,
        "commission_pct": commission_pct,
        "cost_price_total": cost_price_total,
        "margin_profit": margin_profit,
        "margin_profit_pct": margin_profit_pct,
        "margin_clean": margin_clean,
        "margin_clean_pct": margin_clean_pct,
        "roi": roi,
        "profit_per_buyout": profit_per_buyout,
    }

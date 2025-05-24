import math

def estimate_liquidity_amounts(
    P, lower_price, upper_price, amount0_avail, amount1_avail
):
    sqrt_P = math.sqrt(P)
    sqrt_lower = math.sqrt(lower_price)
    sqrt_upper = math.sqrt(upper_price)

    # 计算每单位流动性所需的代币
    delta_x = (1 / sqrt_P) - (1 / sqrt_upper)
    delta_y = sqrt_P - sqrt_lower

    # 计算最大可能的流动性 L
    L_from_token0 = amount0_avail / delta_x if delta_x > 0 else float('inf')
    L_from_token1 = amount1_avail / delta_y if delta_y > 0 else float('inf')
    L = min(L_from_token0, L_from_token1)

    # 预估实际投入数量
    amount0 = L * delta_x
    amount1 = L * delta_y

    return amount0, amount1, L

# 示例
amount0, amount1, L = estimate_liquidity_amounts(
    P=2.99748,
    lower_price=2.6992,
    upper_price=3.3034,
    amount0_avail=73.7501,
    amount1_avail=66.555004
)
print(f"投入 token0: {amount0:.6f}, token1: {amount1:.6f}, 流动性 L: {L:.6f}")
